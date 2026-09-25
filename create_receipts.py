import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

import django
django.setup()

import random
from decimal import Decimal
from django.contrib.auth import get_user_model
from receipts.models import Receipt

User = get_user_model()

try:
    user = User.objects.filter(username='mariano').first() or User.objects.filter(username='test').first()
    if not user:
        user = User.objects.create_user('test', email='test@test.com', password='test')
except Exception as e:
    print('Error buscando usuario:', e)
    user = User.objects.create_user('test', email='test@test.com', password='test')

for i in range(1, 11):
    pv = str(random.randint(1, 99999)).zfill(5)
    num = str(random.randint(10000001, 99999999)).zfill(8)
    monto = Decimal(str(random.randint(200000, 300000)))
    
    Receipt.objects.create(
        user=user,
        archivo_original='receipts/2025/09/test_' + str(i) + '.jpg',
        fecha_emision='15/09/2025',
        cuit_emisor='30712345678',
        razon_social='ASIM LAURA SOLEDAD',
        tipo_comprobante='Factura B',
        letra='B',
        numero_comprobante=f"{pv}-{num}",
        punto_venta=pv,
        numero_solo=num,
        importe_total=monto,
        importe_iva=Decimal('0'),
        categoria_gasto_siradig='Gastos de Adquisición de Indumentaria y Equipamiento',
        origen='upload_web',
        estado='pendiente_carga',
    )
    print(f"Comprobante {i}: PV={pv} Num={num} Monto=${monto}")

print("10 comprobantes creados con datos aleatorios (200000-300000) y puntos de venta variables.")
