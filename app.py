from flask import Flask, request, jsonify, render_template

from simulator import Memory, CPU, Assembler, AssemblerError

app = Flask(__name__)

memory = Memory()
cpu = CPU(memory)
assembler = Assembler()

last_program = {'start_addr': 0, 'machine_code': []}


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/assemble', methods=['POST'])
def api_assemble():
    data = request.get_json(force=True)
    source = data.get('source', '')
    try:
        result = assembler.assemble(source)
        return jsonify(result)
    except AssemblerError as exc:
        return jsonify({'success': False, 'line_no': exc.line_no, 'message': exc.message}), 400
    except Exception as exc:  # noqa: BLE001
        return jsonify({'success': False, 'line_no': 0, 'message': str(exc)}), 400


@app.route('/api/load', methods=['POST'])
def api_load():
    global last_program
    data = request.get_json(force=True)
    start_addr = int(data.get('start_addr', 0))
    machine_code = data.get('machine_code', [])

    memory.load_program(machine_code, start_addr)
    cpu.reset()
    cpu.PC = start_addr & 0xFFF

    last_program = {'start_addr': start_addr, 'machine_code': machine_code}

    return jsonify({
        'success': True,
        'state': cpu.get_state(),
        'memory': memory.dump_nonzero()
    })


@app.route('/api/step', methods=['POST'])
def api_step():
    state = cpu.step()
    return jsonify({
        'state': state,
        'memory': memory.dump_nonzero()
    })


@app.route('/api/run', methods=['POST'])
def api_run():
    data = request.get_json(force=True) if request.data else {}
    max_cycles = int(data.get('max_cycles', 200000))
    state = cpu.run(max_cycles=max_cycles)
    return jsonify({
        'state': state,
        'memory': memory.dump_nonzero()
    })


@app.route('/api/reset', methods=['POST'])
def api_reset():
    memory.reset()
    cpu.reset()
    return jsonify({
        'state': cpu.get_state(),
        'memory': memory.dump_nonzero()
    })


@app.route('/api/state', methods=['GET'])
def api_state():
    return jsonify({
        'state': cpu.get_state(),
        'memory': memory.dump_nonzero()
    })


@app.route('/api/memory', methods=['GET'])
def api_memory():
    start = int(request.args.get('start', 0))
    end = int(request.args.get('end', 255))
    end = min(end, Memory.SIZE - 1)
    cells = [{'addr': a, 'value': memory.read(a)} for a in range(start, end + 1)]
    return jsonify({'cells': cells})


@app.route('/api/memory/write', methods=['POST'])
def api_memory_write():
    data = request.get_json(force=True)
    addr = int(data.get('addr'))
    value = int(data.get('value'))
    memory.write(addr, value)
    return jsonify({'success': True, 'addr': addr, 'value': memory.read(addr)})


@app.route('/api/input', methods=['POST'])
def api_input():
    data = request.get_json(force=True)
    value = int(data.get('value', 0))
    cpu.set_input(value)
    return jsonify({'state': cpu.get_state()})


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
