from flask import Flask, send_file, request, jsonify
import subprocess
import tempfile
import os
import re

app = Flask(__name__)

# Define the paths to the tools
AS_PATH = "csky-elfabiv2-as"
OBJDUMP_PATH = "csky-elfabiv2-objdump"

@app.route('/')
def index():
    return send_file('index.html')

BLACKLIST_HEX = set([
'01', '02', '03', '04', '06', '07', '09', '0a', '0b', '0d', '0e', '0f', '11', '13', '14', '15', '16', '18', '1d', '1e', '1f', '20', '21', '22', '23', '2a', '2b', '2d', '30', '31', '32', '34', '3a', '3b', '3d', '40', '42', '48', '4b', '4e', '50', '54', '5a', '5b', '5d', '5f', '60', '63', '6a', '6b', '6d', '6f', '72', '78', '7b', '7e', '7f', '80', '84', '8a', '8b', '8d', '8f', '90', '95', '9a', '9b', '9d', '9f', 'a2', 'a5', 'ab', 'ad', 'af', 'b2', 'b5', 'bb', 'bd', 'bf', 'c2', 'c8', 'cb', 'cd', 'ce', 'd2', 'd4', 'd5', 'd9', 'da', 'df', 'e4', 'e5', 'e9', 'ed', 'ee', 'f1', 'f2', 'fa'
])

def reorder_opcode_hex(h):
    # h is contiguous hex (no spaces), lowercase
    if len(h) == 4:  # 16-bit instruction
        return h[2:4] + h[0:2]
    if len(h) == 8:  # 32-bit instruction
        return h[2:4] + h[0:2] + h[6:8] + h[4:6]
    # Fallback: try per-16-bit chunks
    out = []
    for i in range(0, len(h), 4):
        chunk = h[i:i+4]
        if len(chunk) == 4:
            out.append(chunk[2:4] + chunk[0:2])
        else:
            out.append(chunk)
    return ''.join(out)

@app.route('/compile', methods=['POST'])
def compile_assembly():
    try:
        assembly_code = request.json.get('assembly', '')
        output_format = request.json.get('format', 'hex')
        if not assembly_code:
            return jsonify({'error': 'No assembly code provided'}), 400
        with tempfile.TemporaryDirectory() as temp_dir:
            asm_file = os.path.join(temp_dir, 'input.s')
            with open(asm_file, 'w') as f:
                f.write(".global _start\n")
                f.write("_start:\n")
                f.write(assembly_code)
            obj_file = os.path.join(temp_dir, 'output.o')
            try:
                subprocess.run([AS_PATH, '-o', obj_file, asm_file], check=True, capture_output=True, text=True)
            except subprocess.CalledProcessError as e:
                return jsonify({'error': 'Assembly compilation failed', 'details': e.stderr}), 400
            try:
                result = subprocess.run([OBJDUMP_PATH, '-d', obj_file], check=True, capture_output=True, text=True)
                objdump_output = result.stdout
                if output_format == 'objdump':
                    return jsonify({'output': objdump_output})
                elif output_format == 'hex':
                    hex_lines = []
                    blacklisted = False
                    blacklisted_bytes = set()
                    for line in objdump_output.split('\n'):
                        m = re.search(r'^\s*[0-9a-f]+:\s+([0-9a-f ]+)', line)
                        if not m:
                            continue
                        raw_hex = m.group(1).strip().replace(' ', '').lower()
                        if not raw_hex:
                            continue
                        # Reorder per instruction size
                        out_hex = reorder_opcode_hex(raw_hex)
                        hex_lines.append(out_hex)

                        # Blacklist check (on output bytes)
                        for i in range(0, len(out_hex), 2):
                            byte = out_hex[i:i+2]
                            if byte in BLACKLIST_HEX:
                                blacklisted = True
                                blacklisted_bytes.add(byte)

                    resp = {'output': '\n'.join(hex_lines)}
                    if blacklisted:
                        resp['error'] = 'hex blacklisted: ' + ', '.join(sorted(blacklisted_bytes))
                    return jsonify(resp)
                else:
                    return jsonify({'error': 'Invalid output format'}), 400
            except subprocess.CalledProcessError as e:
                return jsonify({'error': 'Objdump failed', 'details': e.stderr}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host="0.0.0.0", debug=True)
