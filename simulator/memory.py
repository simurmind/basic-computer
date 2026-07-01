class Memory:
    SIZE = 4096
    WORD_MASK = 0xFFFF
    ADDR_MASK = 0xFFF

    def __init__(self):
        self.cells = [0] * Memory.SIZE

    def read(self, addr):
        return self.cells[addr & Memory.ADDR_MASK]

    def write(self, addr, value):
        self.cells[addr & Memory.ADDR_MASK] = value & Memory.WORD_MASK

    def load_program(self, machine_code, start_addr=0):
        for offset, word in enumerate(machine_code):
            self.write(start_addr + offset, word)

    def reset(self):
        self.cells = [0] * Memory.SIZE

    def dump(self):
        return list(self.cells)

    def dump_nonzero(self):
        return {addr: val for addr, val in enumerate(self.cells) if val != 0}
