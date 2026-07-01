class Bus:
    """
    Simulates the common bus of the Basic Computer.
    Every data transfer between registers/memory MUST go through this
    object so the frontend can highlight which lines are active.
    """

    REGISTER_LINES = {
        'AR': 1, 'PC': 2, 'DR': 3, 'AC': 4,
        'IR': 5, 'TR': 6, 'MEM': 7, 'INPR': 8, 'OUTR': 9
    }

    def __init__(self, cpu):
        self.cpu = cpu
        self.active_src = None
        self.active_dst = None
        self.last_value = 0

    def transfer(self, src_name, dst_name, value, width_mask=0xFFFF):
        """
        Registers a transfer of `value` from src_name to dst_name on the bus.
        The caller is responsible for actually assigning the destination
        register (the bus only mediates/announces the transfer so the UI
        can visualize it), mirroring how the physical bus carries the
        value while the destination register's load-enable line latches it.
        """
        value &= width_mask
        self.active_src = src_name
        self.active_dst = dst_name
        self.last_value = value
        self.cpu.log(f"BUS  {src_name} -> {dst_name}  = {value:04X}h")
        return value

    def snapshot(self):
        return {
            'src': self.active_src,
            'dst': self.active_dst,
            'value': self.last_value
        }

    def clear(self):
        self.active_src = None
        self.active_dst = None
