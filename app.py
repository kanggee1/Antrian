import os
import time
import json
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_from_directory
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'kunci_rahasia_admin_percetakan'

# PERBAIKAN: Gunakan jalur absolut agar hosting tidak salah tempat menyimpan foto/database
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

DB_FILE = os.path.join(BASE_DIR, 'db_antrian.json')

def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r') as f:
                data = json.load(f)
                return data.get('db_antrian', []), data.get('current_id', 1)
        except:
            pass
    return [], 1

def save_db(db_antrian, current_id):
    try:
        with open(DB_FILE, 'w') as f:
            json.dump({'db_antrian': db_antrian, 'current_id': current_id}, f)
    except:
        pass

ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = 'nabati123'

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('logged_in'):
        return redirect(url_for('admin'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('admin'))
        else:
            return render_template('login.html', error="Username atau Password salah!")
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/admin')
def admin():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template('admin.html')

@app.route('/display')
def display():
    return render_template('display.html')

@app.route('/api/submit', methods=['POST'])
def submit_order():
    db_antrian, current_id = load_db()
    
    files = request.files.getlist('file_upload')
    nama = request.form.get('nama')
    no_order = request.form.get('no_order')

    if not files or files[0].filename == '':
        return "File kosong", 400

    saved_filenames = []
    for i, file in enumerate(files):
        if file and file.filename != '':
            filename = secure_filename(f"{int(time.time())}_{i}_{file.filename}")
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            saved_filenames.append(filename)
            
    order = {
        'id': current_id,
        'nama': nama,
        'no_order': no_order,
        'filenames': saved_filenames, 
        'status': 'Menunggu',
        'waktu': time.strftime("%Y-%m-%d %H:%M:%S")
    }
    db_antrian.append(order)
    current_id += 1
    
    save_db(db_antrian, current_id)
    
    return '''
    <script>
        alert("Berhasil! Antrian Anda sudah masuk.");
        window.location.href = "/";
    </script>
    '''

@app.route('/api/queue')
def get_queue():
    db_antrian, _ = load_db()
    menunggu = [q for q in db_antrian if q['status'] == 'Menunggu']
    return jsonify(menunggu)

@app.route('/api/history')
def get_history():
    db_antrian, _ = load_db()
    riwayat = [q for q in db_antrian if q['status'] in ['Selesai', 'Dilewati']]
    return jsonify(riwayat)

@app.route('/api/update_status/<int:order_id>', methods=['POST'])
def update_status(order_id):
    db_antrian, current_id = load_db()
    data = request.json
    status_baru = data.get('status')
    
    updated = False
    for order in db_antrian:
        if order['id'] == order_id:
            order['status'] = status_baru
            updated = True
            break
            
    if updated:
        save_db(db_antrian, current_id)
        return jsonify({"success": True, "message": "Status diperbarui"})
            
    return jsonify({"success": False, "message": "Order tidak ditemukan"}), 404

@app.route('/api/delete/<int:order_id>', methods=['DELETE'])
def delete_order(order_id):
    db_antrian, current_id = load_db()
    
    order_to_delete = None
    for order in db_antrian:
        if order['id'] == order_id:
            order_to_delete = order
            break
            
    if order_to_delete:
        for filename in order_to_delete.get('filenames', []):
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except:
                    pass
                    
        db_antrian = [o for o in db_antrian if o['id'] != order_id]
        save_db(db_antrian, current_id)
        
        return jsonify({"success": True, "message": "Riwayat dan file berhasil dihapus secara permanen"})
        
    return jsonify({"success": False, "message": "Data tidak ditemukan"}), 404

@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True, port=5000)