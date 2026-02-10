import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import qrcode

app = Flask(__name__)
app.config['SECRET_KEY'] = 'mi_secreto_super_seguro'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///mantenimiento.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- MODELOS DE LA BASE DE DATOS ---

class Maquina(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    codigo = db.Column(db.String(4), unique=True, nullable=False) # El código de 4 dígitos
    descripcion = db.Column(db.Text)
    fecha_alta = db.Column(db.DateTime, default=datetime.utcnow)
    # Relación con fallas
    fallas = db.relationship('Falla', backref='maquina', lazy=True)

class Falla(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    descripcion = db.Column(db.Text, nullable=False)
    solucion = db.Column(db.Text, nullable=True) # Si ya se arregló
    estado = db.Column(db.String(20), default='Pendiente') # Pendiente, En Proceso, Resuelto
    tecnico = db.Column(db.String(50))
    fecha_reporte = db.Column(db.DateTime, default=datetime.utcnow)
    maquina_id = db.Column(db.Integer, db.ForeignKey('maquina.id'), nullable=False)

# --- HELPER PARA QR ---
def generar_qr(codigo):
    # El QR apuntará a la URL de la máquina
    # En local será http://127.0.0.1:5000/maquina/CODIGO
    url_data = f"http://127.0.0.1:5000/maquina/{codigo}"
    qr = qrcode.make(url_data)
    ruta = os.path.join('static', 'qrcodes', f'{codigo}.png')
    qr.save(ruta)

# --- RUTAS ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/buscar', methods=['POST'])
def buscar():
    codigo = request.form.get('codigo')
    maquina = Maquina.query.filter_by(codigo=codigo).first()
    if maquina:
        return redirect(url_for('ver_maquina', codigo=codigo))
    else:
        flash('Máquina no encontrada', 'error')
        return redirect(url_for('index'))

@app.route('/maquina/<codigo>', methods=['GET', 'POST'])
def ver_maquina(codigo):
    maquina = Maquina.query.filter_by(codigo=codigo).first_or_404()
    
    if request.method == 'POST':
        # Agregar nueva falla
        descripcion = request.form.get('descripcion')
        tecnico = request.form.get('tecnico')
        nueva_falla = Falla(descripcion=descripcion, tecnico=tecnico, maquina_id=maquina.id)
        db.session.add(nueva_falla)
        db.session.commit()
        return redirect(url_for('ver_maquina', codigo=codigo))

    return render_template('maquina.html', maquina=maquina)

@app.route('/falla/actualizar/<int:id>', methods=['POST'])
def actualizar_falla(id):
    falla = Falla.query.get_or_404(id)
    falla.solucion = request.form.get('solucion')
    falla.estado = request.form.get('estado')
    db.session.commit()
    return redirect(url_for('ver_maquina', codigo=falla.maquina.codigo))

@app.route('/admin/crear', methods=['GET', 'POST'])
def crear_maquina():
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        codigo = request.form.get('codigo')
        desc = request.form.get('descripcion')
        
        existe = Maquina.query.filter_by(codigo=codigo).first()
        if existe:
            flash('Ese código ya existe', 'error')
        else:
            nueva = Maquina(nombre=nombre, codigo=codigo, descripcion=desc)
            db.session.add(nueva)
            db.session.commit()
            
            # Generar QR
            if not os.path.exists(os.path.join('static', 'qrcodes')):
                os.makedirs(os.path.join('static', 'qrcodes'))
            generar_qr(codigo)
            
            return redirect(url_for('ver_maquina', codigo=codigo))
            
    return render_template('crear.html')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    # Ejecutar accesible en red local con certificado SSL temporal
    app.run(debug=True, host='0.0.0.0')