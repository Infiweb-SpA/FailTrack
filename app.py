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
    codigo = db.Column(db.String(4), unique=True, nullable=False)
    descripcion = db.Column(db.Text)
    fecha_alta = db.Column(db.DateTime, default=datetime.utcnow)
    fallas = db.relationship('Falla', backref='maquina', lazy=True)

class Falla(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    descripcion = db.Column(db.Text, nullable=False)
    estado = db.Column(db.String(30), default='Pendiente') # Pendiente, En Proceso, Espera Repuestos, Resuelto
    tecnico = db.Column(db.String(50))
    fecha_reporte = db.Column(db.DateTime, default=datetime.utcnow)
    maquina_id = db.Column(db.Integer, db.ForeignKey('maquina.id'), nullable=False)
    # Relación con la bitácora de comentarios
    comentarios = db.relationship('Comentario', backref='falla', lazy=True)

class Comentario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    texto = db.Column(db.Text, nullable=False)
    autor = db.Column(db.String(50), nullable=True)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    falla_id = db.Column(db.Integer, db.ForeignKey('falla.id'), nullable=False)

# --- HELPER PARA QR ---
def generar_qr_con_url(codigo, base_url):
    # Aseguramos que no haya barras dobles y creamos el link
    link_final = f"{base_url.rstrip('/')}/maquina/{codigo}"
    
    qr = qrcode.QRCode(box_size=10, border=4)
    qr.add_data(link_final)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Ruta de guardado
    ruta_dir = os.path.join('static', 'qrcodes')
    if not os.path.exists(ruta_dir):
        os.makedirs(ruta_dir)
        
    img.save(os.path.join(ruta_dir, f'{codigo}.png'))

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
        # Reportar nueva falla
        descripcion = request.form.get('descripcion')
        tecnico = request.form.get('tecnico')
        
        nueva_falla = Falla(descripcion=descripcion, tecnico=tecnico, maquina_id=maquina.id)
        db.session.add(nueva_falla)
        db.session.commit()
        return redirect(url_for('ver_maquina', codigo=codigo))

    return render_template('maquina.html', maquina=maquina)

@app.route('/falla/comentar/<int:id>', methods=['POST'])
def agregar_comentario(id):
    falla = Falla.query.get_or_404(id)
    
    texto_comentario = request.form.get('comentario')
    autor = request.form.get('autor_comentario')
    nuevo_estado = request.form.get('estado')

    # 1. Guardar comentario si existe texto
    if texto_comentario:
        nuevo_coment = Comentario(texto=texto_comentario, autor=autor, falla_id=falla.id)
        db.session.add(nuevo_coment)
    
    # 2. Actualizar estado
    if nuevo_estado:
        falla.estado = nuevo_estado

    db.session.commit()
    return redirect(url_for('ver_maquina', codigo=falla.maquina.codigo))

@app.route('/admin/crear', methods=['GET', 'POST'])
def crear_maquina():
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        codigo = request.form.get('codigo')
        desc = request.form.get('descripcion')
        
        # Validación de existencia
        existe = Maquina.query.filter_by(codigo=codigo).first()
        if existe:
            flash(f'El código {codigo} ya existe', 'error')
            return redirect(url_for('crear_maquina'))
        
        try:
            # Guardar en BD
            nueva = Maquina(nombre=nombre, codigo=codigo, descripcion=desc)
            db.session.add(nueva)
            db.session.commit()

            # --- FUERZA AQUÍ TU URL DE DEV TUNNELS ---
            # Si request.host_url da localhost, ponemos la URL fija:
            url_publica = "https://m1g85s7v-5000.brs.devtunnels.ms"
            
            generar_qr_con_url(codigo, url_publica)
            
            flash('Máquina y QR creados con éxito', 'success')
            return redirect(url_for('ver_maquina', codigo=codigo))
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'error')
            
    return render_template('crear.html')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    # Host 0.0.0.0 permite acceso desde la red local
    app.run(debug=True, host='0.0.0.0')