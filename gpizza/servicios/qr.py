"""RF-009 Registro con código QR / barras: genera las imágenes de los códigos.

Cada producto tiene su código (YP000001...) y cada pedido su folio (YP-0001). Un lector de códigos
USB funciona como un teclado: "escribe" el código y Enter, así que sirve en cualquier campo de texto;
con el celular, la cámara lee el QR con html5-qrcode.
"""
import io

import qrcode


def png(texto: str, tamano_caja: int = 8) -> bytes:
    codigo = qrcode.QRCode(box_size=tamano_caja, border=2, error_correction=qrcode.constants.ERROR_CORRECT_M)
    codigo.add_data(texto)
    codigo.make(fit=True)
    salida = io.BytesIO()
    codigo.make_image().save(salida, format='PNG')  # dibuja con Pillow
    return salida.getvalue()
