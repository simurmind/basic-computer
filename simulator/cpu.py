import time
from .bus import Bus

WORD_MASK = 0xFFFF
ADDR_MASK = 0xFFF

MRI_NAMES = {0: 'AND', 1: 'ADD', 2: 'LDA', 3: 'STA', 4: 'BUN', 5: 'BSA', 6: 'ISZ'}

RRI_BITS = [
    ('CLA', 0x800), ('CLE', 0x400), ('CMA', 0x200), ('CME', 0x100),
    ('CIR', 0x080), ('CIL', 0x040), ('INC', 0x020), ('SPA', 0x010),
    ('SNA', 0x008), ('SZA', 0x004), ('SZE', 0x002), ('HLT', 0x001)
]

IO_BITS = [
    ('INP', 0x800), ('OUT', 0x400), ('SKI', 0x200),
    ('SKO', 0x100), ('ION', 0x080), ('IOF', 0x040)
]


class CPU:
    def __init__(self, memory):
        self.memory = memory
        self.bus = Bus(self)
        self.reset()

    # ------------------------------------------------------------------ #
    def reset(self):
        self.AC = 0
        self.PC = 0
        self.AR = 0
        self.DR = 0
        self.IR = 0
        self.TR = 0
        self.INPR = 0
        self.OUTR = 0
        self.SC = 0
        self.E = 0
        self.S = 1          # 1 = running, 0 = halted
        self.IEN = 0
        self.FGI = 0
        self.FGO = 0
        self.I = 0
        self.opcode = 0
        self.current_mnemonic = ''
        self.phase = 'FETCH'
        self.micro_ops = []
        self.history = []
        self.bus.clear()
        self.cycle_count = 0

    # ------------------------------------------------------------------ #
    def log(self, message):
        self.history.append({
            'time': time.strftime('%H:%M:%S'),
            'sc': self.SC,
            'phase': self.phase,
            'message': message
        })
        if len(self.history) > 500:
            self.history.pop(0)

    # ------------------------------------------------------------------ #
    def get_state(self):
        return {
            'AC': self.AC, 'PC': self.PC, 'AR': self.AR, 'DR': self.DR,
            'IR': self.IR, 'TR': self.TR, 'INPR': self.INPR, 'OUTR': self.OUTR,
            'SC': self.SC, 'E': self.E, 'S': self.S, 'IEN': self.IEN,
            'FGI': self.FGI, 'FGO': self.FGO, 'I': self.I,
            'phase': self.phase,
            'mnemonic': self.current_mnemonic,
            'bus': self.bus.snapshot(),
            'history': self.history[-50:],
            'halted': self.S == 0,
            'cycle_count': self.cycle_count
        }

    # ------------------------------------------------------------------ #
    def _begin_instruction(self):
        self.SC = 0
        self.phase = 'FETCH'
        self.bus.clear()
        self.micro_ops = [self._t0_fetch, self._t1_fetch, self._t2_decode]

    def step(self):
        if not self.S:
            return self.get_state()

        if not self.micro_ops:
            self._begin_instruction()

        op = self.micro_ops.pop(0)
        op()
        self.SC = (self.SC + 1) & 0xF

        if not self.micro_ops:
            self.cycle_count += 1

        return self.get_state()

    def run(self, max_cycles=200000):
        steps = 0
        self.bus.clear()
        while self.S and steps < max_cycles:
            self.step()
            steps += 1
        return self.get_state()

    # ------------------------------ FETCH ----------------------------- #
    def _t0_fetch(self):
        self.phase = 'FETCH'
        self.AR = self.bus.transfer('PC', 'AR', self.PC, ADDR_MASK)

    def _t1_fetch(self):
        self.phase = 'FETCH'
        word = self.memory.read(self.AR)
        self.IR = self.bus.transfer('MEM', 'IR', word)
        self.PC = (self.PC + 1) & ADDR_MASK
        self.log(f"PC <- PC + 1 = {self.PC:03X}h")

    # ------------------------------ DECODE ----------------------------- #
    def _t2_decode(self):
        self.phase = 'DECODE'
        self.I = (self.IR >> 15) & 1
        self.opcode = (self.IR >> 12) & 0x7
        addr_field = self.IR & ADDR_MASK
        self.AR = self.bus.transfer('IR', 'AR', addr_field, ADDR_MASK)
        self.log(f"Decode: opcode={self.opcode} I={self.I}")

        if self.opcode == 7:
            if self.I == 0:
                self.current_mnemonic = self._rri_name()
                self.phase = 'EXECUTE'
                self.micro_ops.append(self._exec_rri)
            else:
                self.current_mnemonic = self._io_name()
                self.phase = 'EXECUTE'
                self.micro_ops.append(self._exec_io)
        else:
            self.current_mnemonic = MRI_NAMES.get(self.opcode, '?')
            if self.I == 1:
                self.phase = 'INDIRECT'
                self.micro_ops.append(self._t3_indirect)
            else:
                self.phase = 'EXECUTE'
            self.micro_ops.append(self._exec_mri)

    def _rri_name(self):
        for name, bit in RRI_BITS:
            if self.IR & bit:
                return name
        return 'RRI?'

    def _io_name(self):
        for name, bit in IO_BITS:
            if self.IR & bit:
                return name
        return 'IO?'

    # ----------------------------- INDIRECT ----------------------------- #
    def _t3_indirect(self):
        self.phase = 'INDIRECT'
        word = self.memory.read(self.AR)
        self.AR = self.bus.transfer('MEM', 'AR', word, ADDR_MASK)
        self.log(f"Indirect: AR <- M[AR] = {self.AR:03X}h")

    # ------------------------------ EXECUTE: MRI ------------------------ #
    def _exec_mri(self):
        self.phase = 'EXECUTE'
        op = self.opcode

        if op == 0:   # AND
            word = self.memory.read(self.AR)
            self.DR = self.bus.transfer('MEM', 'DR', word)
            self.AC = self.AC & self.DR
            self.log(f"AC <- AC AND DR = {self.AC:04X}h")

        elif op == 1:  # ADD
            word = self.memory.read(self.AR)
            self.DR = self.bus.transfer('MEM', 'DR', word)
            result = self.AC + self.DR
            self.E = 1 if result > WORD_MASK else 0
            self.AC = self.bus.transfer('DR', 'AC', result, WORD_MASK)
            self.log(f"AC <- AC + DR = {self.AC:04X}h, E={self.E}")

        elif op == 2:  # LDA
            word = self.memory.read(self.AR)
            self.DR = self.bus.transfer('MEM', 'DR', word)
            self.AC = self.bus.transfer('DR', 'AC', self.DR)
            self.log(f"AC <- DR = {self.AC:04X}h")

        elif op == 3:  # STA
            self.memory.write(self.AR, self.AC)
            self.bus.transfer('AC', 'MEM', self.AC)
            self.log(f"M[{self.AR:03X}h] <- AC")

        elif op == 4:  # BUN
            self.PC = self.bus.transfer('AR', 'PC', self.AR, ADDR_MASK)
            self.log(f"PC <- AR = {self.PC:03X}h")

        elif op == 5:  # BSA
            self.memory.write(self.AR, self.PC)
            self.bus.transfer('PC', 'MEM', self.PC, ADDR_MASK)
            self.PC = (self.AR + 1) & ADDR_MASK
            self.log(f"M[{self.AR:03X}h] <- PC, PC <- AR + 1 = {self.PC:03X}h")

        elif op == 6:  # ISZ
            word = self.memory.read(self.AR)
            self.DR = self.bus.transfer('MEM', 'DR', word)
            self.DR = (self.DR + 1) & WORD_MASK
            self.memory.write(self.AR, self.DR)
            if self.DR == 0:
                self.PC = (self.PC + 1) & ADDR_MASK
            self.log(f"M[{self.AR:03X}h] <- DR + 1 = {self.DR:04X}h")

    # ------------------------------ EXECUTE: RRI ------------------------ #
    def _exec_rri(self):
        self.phase = 'EXECUTE'
        ir = self.IR

        if ir & 0x800:  # CLA
            self.AC = 0
            self.log("CLA: AC <- 0")
        if ir & 0x400:  # CLE
            self.E = 0
            self.log("CLE: E <- 0")
        if ir & 0x200:  # CMA
            self.AC = (~self.AC) & WORD_MASK
            self.log(f"CMA: AC <- ~AC = {self.AC:04X}h")
        if ir & 0x100:  # CME
            self.E = 1 - self.E
            self.log(f"CME: E <- ~E = {self.E}")
        if ir & 0x080:  # CIR
            lsb = self.AC & 1
            self.AC = (self.AC >> 1) | (self.E << 15)
            self.E = lsb
            self.log(f"CIR: AC={self.AC:04X}h E={self.E}")
        if ir & 0x040:  # CIL
            msb = (self.AC >> 15) & 1
            self.AC = ((self.AC << 1) | self.E) & WORD_MASK
            self.E = msb
            self.log(f"CIL: AC={self.AC:04X}h E={self.E}")
        if ir & 0x020:  # INC
            self.AC = (self.AC + 1) & WORD_MASK
            self.log(f"INC: AC <- AC + 1 = {self.AC:04X}h")
        if ir & 0x010:  # SPA
            if (self.AC >> 15) & 1 == 0:
                self.PC = (self.PC + 1) & ADDR_MASK
                self.log("SPA: skipped next instruction")
        if ir & 0x008:  # SNA
            if (self.AC >> 15) & 1 == 1:
                self.PC = (self.PC + 1) & ADDR_MASK
                self.log("SNA: skipped next instruction")
        if ir & 0x004:  # SZA
            if self.AC == 0:
                self.PC = (self.PC + 1) & ADDR_MASK
                self.log("SZA: skipped next instruction")
        if ir & 0x002:  # SZE
            if self.E == 0:
                self.PC = (self.PC + 1) & ADDR_MASK
                self.log("SZE: skipped next instruction")
        if ir & 0x001:  # HLT
            self.S = 0
            self.log("HLT: processor stopped")

    # ------------------------------ EXECUTE: I/O ------------------------ #
    def _exec_io(self):
        self.phase = 'EXECUTE'
        ir = self.IR

        if ir & 0x800:  # INP
            self.AC = self.bus.transfer('INPR', 'AC', (self.AC & 0xFF00) | self.INPR)
            self.FGI = 0
            self.log(f"INP: AC(0-7) <- INPR = {self.INPR:02X}h")
        if ir & 0x400:  # OUT
            self.OUTR = self.bus.transfer('AC', 'OUTR', self.AC & 0xFF, 0xFF)
            self.FGO = 0
            self.log(f"OUT: OUTR <- AC(0-7) = {self.OUTR:02X}h")
        if ir & 0x200:  # SKI
            if self.FGI == 1:
                self.PC = (self.PC + 1) & ADDR_MASK
                self.log("SKI: skipped next instruction")
        if ir & 0x100:  # SKO
            if self.FGO == 1:
                self.PC = (self.PC + 1) & ADDR_MASK
                self.log("SKO: skipped next instruction")
        if ir & 0x080:  # ION
            self.IEN = 1
            self.log("ION: IEN <- 1")
        if ir & 0x040:  # IOF
            self.IEN = 0
            self.log("IOF: IEN <- 0")

    # ------------------------------------------------------------------ #
    def set_input(self, value):
        self.INPR = value & 0xFF
        self.FGI = 1
        self.log(f"External device set INPR = {self.INPR:02X}h, FGI=1")
