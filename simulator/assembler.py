class AssemblerError(Exception):
    def __init__(self, line_no, message):
        self.line_no = line_no
        self.message = message
        super().__init__(f"Line {line_no}: {message}")


MRI_OPCODES = {
    'AND': 0x0, 'ADD': 0x1, 'LDA': 0x2, 'STA': 0x3,
    'BUN': 0x4, 'BSA': 0x5, 'ISZ': 0x6
}

RRI_OPCODES = {
    'CLA': 0x7800, 'CLE': 0x7400, 'CMA': 0x7200, 'CME': 0x7100,
    'CIR': 0x7080, 'CIL': 0x7040, 'INC': 0x7020, 'SPA': 0x7010,
    'SNA': 0x7008, 'SZA': 0x7004, 'SZE': 0x7002, 'HLT': 0x7001
}

IO_OPCODES = {
    'INP': 0xF800, 'OUT': 0xF400, 'SKI': 0xF200,
    'SKO': 0xF100, 'ION': 0xF080, 'IOF': 0xF040
}

PSEUDO_OPS = {'ORG', 'DEC', 'HEX', 'END'}


def _strip_comment(line):
    for marker in ('/', '#', ';'):
        idx = line.find(marker)
        if idx != -1:
            line = line[:idx]
    return line.strip()


def _tokenize(line):
    line = line.replace(',', ' , ')
    return [t for t in line.split() if t]


class Assembler:
    def __init__(self):
        self.symbol_table = {}
        self.listing = []
        self.errors = []

    def assemble(self, source_text):
        self.symbol_table = {}
        self.listing = []
        self.errors = []

        raw_lines = source_text.splitlines()
        parsed_lines = []
        loc = 0

        # Pass 1: build symbol table, compute addresses
        for line_no, raw in enumerate(raw_lines, start=1):
            text = _strip_comment(raw)
            if not text:
                continue
            tokens = _tokenize(text)
            if not tokens:
                continue

            label = None
            if len(tokens) >= 2 and tokens[1] == ',':
                label = tokens[0].upper()
                tokens = tokens[2:]
            elif tokens[0].endswith(':'):
                label = tokens[0][:-1].upper()
                tokens = tokens[1:]

            if not tokens:
                if label:
                    self.symbol_table[label] = loc
                continue

            mnemonic = tokens[0].upper()

            if mnemonic == 'ORG':
                if len(tokens) < 2:
                    raise AssemblerError(line_no, "ORG requires an address")
                loc = int(tokens[1], 16)
                if label:
                    self.symbol_table[label] = loc
                continue

            if mnemonic == 'END':
                break

            if label:
                if label in self.symbol_table:
                    raise AssemblerError(line_no, f"Duplicate label '{label}'")
                self.symbol_table[label] = loc

            parsed_lines.append({
                'line_no': line_no, 'addr': loc,
                'mnemonic': mnemonic, 'tokens': tokens, 'label': label
            })
            loc += 1

        # Pass 2: generate machine code
        machine_code = {}
        for entry in parsed_lines:
            line_no = entry['line_no']
            addr = entry['addr']
            mnemonic = entry['mnemonic']
            tokens = entry['tokens']

            word = self._encode(mnemonic, tokens, line_no)
            machine_code[addr] = word & 0xFFFF
            self.listing.append({
                'addr': addr, 'word': word & 0xFFFF,
                'source': ' '.join(tokens),
                'label': entry['label'] or ''
            })

        if not machine_code:
            raise AssemblerError(0, "No instructions assembled")

        start_addr = min(machine_code.keys())
        end_addr = max(machine_code.keys())
        words = [machine_code.get(a, 0) for a in range(start_addr, end_addr + 1)]

        return {
            'success': True,
            'start_addr': start_addr,
            'machine_code': words,
            'listing': self.listing,
            'symbol_table': self.symbol_table
        }

    def _encode(self, mnemonic, tokens, line_no):
        if mnemonic in MRI_OPCODES:
            if len(tokens) < 2:
                raise AssemblerError(line_no, f"{mnemonic} requires an operand")
            operand = tokens[1].upper()
            indirect = len(tokens) >= 3 and tokens[2].upper() == 'I'

            if operand in self.symbol_table:
                address = self.symbol_table[operand]
            else:
                try:
                    address = int(operand, 16)
                except ValueError:
                    raise AssemblerError(line_no, f"Unknown symbol '{operand}'")

            opcode = MRI_OPCODES[mnemonic]
            word = (1 if indirect else 0) << 15
            word |= opcode << 12
            word |= address & 0xFFF
            return word

        if mnemonic in RRI_OPCODES:
            return RRI_OPCODES[mnemonic]

        if mnemonic in IO_OPCODES:
            return IO_OPCODES[mnemonic]

        if mnemonic == 'DEC':
            if len(tokens) < 2:
                raise AssemblerError(line_no, "DEC requires a value")
            value = int(tokens[1])
            return value & 0xFFFF

        if mnemonic == 'HEX':
            if len(tokens) < 2:
                raise AssemblerError(line_no, "HEX requires a value")
            value = int(tokens[1], 16)
            return value & 0xFFFF

        raise AssemblerError(line_no, f"Unknown mnemonic '{mnemonic}'")
