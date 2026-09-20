import os
import time
import json
import zipfile
import io
import csv
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_from_directory, send_file, Response
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'kunci_rahasia_admin_percetakan'

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

# FUNGSI BARU: Menghitung ukuran folder penyimpanan (Storage Monitor)
def get_dir_size(path):
    total = 0
    try:
        for dirpath, _, filenames in os.walk(path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                if not os.path.islink(fp):
                    total += os.path.getsize(fp)
    except:
        pass
    return total

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
        'waktu': time.strftime("%Y-%m-%d %H:%M:%S"),
        'priority': False
    }
    db_antrian.append(order)
    current_id += 1
    save_db(db_antrian, current_id)
    
    return '''
    <script>
        alert("Berhasil! Approval anda sudah Terkirim.");
        window.location.href = "/";
    </script>
    '''

@app.route('/api/queue')
def get_queue():
    db_antrian, _ = load_db()
    menunggu = [q for q in db_antrian if q['status'] == 'Menunggu']
    menunggu.sort(key=lambda x: (not x.get('priority', False), x['id']))
    return jsonify(menunggu)

@app.route('/api/history')
def get_history():
    db_antrian, _ = load_db()
    search_query = request.args.get('q', '').lower()
    filter_date = request.args.get('date', '')
    filter_status = request.args.get('status', '')
    
    riwayat = [q for q in db_antrian if q['status'] in ['Selesai', 'Dilewati']]
    
    if filter_status:
        riwayat = [q for q in riwayat if q['status'] == filter_status]
        
    if filter_date:
        riwayat = [q for q in riwayat if q.get('waktu', '').startswith(filter_date)]
        
    if search_query:
        riwayat = [q for q in riwayat if search_query in q['nama'].lower() or search_query in q['no_order'].lower()]
    
    riwayat.sort(key=lambda x: x.get('waktu', ''), reverse=True)
    return jsonify(riwayat)

# API BARU: Mendapatkan status ruang penyimpanan server
@app.route('/api/system_stats')
def system_stats():
    size_bytes = get_dir_size(app.config['UPLOAD_FOLDER'])
    size_mb = size_bytes / (1024 * 1024)
    # Jika lebih dari 1000MB, ubah ke GB
    if size_mb > 1000:
        return jsonify({"storage": f"{round(size_mb / 1024, 2)} GB"})
    return jsonify({"storage": f"{round(size_mb, 2)} MB"})

@app.route('/api/update_status/<int:order_id>', methods=['POST'])
def update_status(order_id):
    db_antrian, current_id = load_db()
    data = request.json
    status_baru = data.get('status')
    
    updated = False
    for order in db_antrian:
        if order['id'] == order_id:
            order['status'] = status_baru
            if status_baru != 'Menunggu':
                order['priority'] = False
            updated = True
            break
            
    if updated:
        save_db(db_antrian, current_id)
        return jsonify({"success": True, "message": "Status diperbarui"})
            
    return jsonify({"success": False, "message": "Order tidak ditemukan"}), 404

@app.route('/api/toggle_priority/<int:order_id>', methods=['POST'])
def toggle_priority(order_id):
    db_antrian, current_id = load_db()
    updated = False
    for order in db_antrian:
        if order['id'] == order_id:
            order['priority'] = not order.get('priority', False)
            updated = True
            break
            
    if updated:
        save_db(db_antrian, current_id)
        return jsonify({"success": True, "message": "Status VIP diperbarui"})
    return jsonify({"success": False}), 404

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

@app.route('/api/bulk_delete', methods=['POST'])
def bulk_delete():
    db_antrian, current_id = load_db()
    data = request.json
    ids_to_delete = data.get('ids', [])
    
    if not ids_to_delete:
        return jsonify({"success": False, "message": "Tidak ada ID yang dikirim"}), 400
        
    orders_to_delete = [q for q in db_antrian if q['id'] in ids_to_delete]
    
    for order in orders_to_delete:
        for filename in order.get('filenames', []):
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception:
                    pass
                    
    db_antrian = [o for o in db_antrian if o['id'] not in ids_to_delete]
    save_db(db_antrian, current_id)
    return jsonify({"success": True, "message": f"{len(ids_to_delete)} riwayat berhasil dihapus secara massal."})

@app.route('/api/delete_all_history', methods=['DELETE'])
def delete_all_history():
    db_antrian, current_id = load_db()
    antrian_aktif = [q for q in db_antrian if q['status'] == 'Menunggu']
    antrian_selesai = [q for q in db_antrian if q['status'] in ['Selesai', 'Dilewati']]
    
    for order in antrian_selesai:
        for filename in order.get('filenames', []):
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception:
                    pass
                    
    save_db(antrian_aktif, current_id)
    return jsonify({"success": True, "message": "Semua riwayat dan file usang berhasil dibersihkan dari server."})

@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

@app.route('/api/download_zip/<int:order_id>')
def download_zip(order_id):
    db_antrian, _ = load_db()
    order = next((q for q in db_antrian if q['id'] == order_id), None)
    
    if not order or not order.get('filenames'):
        return "Pesanan tidak ditemukan atau tidak ada file", 404
        
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for filename in order['filenames']:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            if os.path.exists(file_path):
                clean_name = filename.split('_', 2)[-1] if '_' in filename else filename
                zf.write(file_path, arcname=clean_name)
                
    memory_file.seek(0)
    safe_order_name = secure_filename(order['nama'])
    zip_filename = f"Order_{order['no_order']}_{safe_order_name}.zip"
    
    return send_file(memory_file, download_name=zip_filename, as_attachment=True)

@app.route('/api/export_csv')
def export_csv():
    db_antrian, _ = load_db()
    riwayat = [q for q in db_antrian if q['status'] in ['Selesai', 'Dilewati']]
    riwayat.sort(key=lambda x: x.get('waktu', ''), reverse=True)
    
    def generate():
        data = io.StringIO()
        writer = csv.writer(data, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        writer.writerow(['ID Database', 'No Order', 'Nama Pelanggan', 'Status', 'Tanggal & Waktu', 'Jumlah File Diproses'])
        yield data.getvalue()
        data.seek(0)
        data.truncate(0)
        
        for q in riwayat:
            writer.writerow([
                q['id'],
                q['no_order'],
                q['nama'],
                q['status'],
                q['waktu'],
                len(q.get('filenames', []))
            ])
            yield data.getvalue()
            data.seek(0)
            data.truncate(0)
            
    response = Response(generate(), mimetype='text/csv')
    response.headers.set("Content-Disposition", "attachment", filename=f"Laporan_Cetak_{datetime.now().strftime('%Y%m%d')}.csv")
    return response

if __name__ == '__main__':
    app.run(debug=True, port=5000)
