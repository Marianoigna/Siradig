from rest_framework import serializers

from .models import Receipt


class ReceiptSerializer(serializers.ModelSerializer):
    class Meta:
        model = Receipt
        fields = [
            'id', 'fecha_emision', 'cuit_emisor', 'razon_social', 'tipo_comprobante',
            'letra', 'numero_comprobante', 'importe_total', 'importe_iva',
            'categoria_gasto_siradig', 'origen', 'estado', 'created_at',
        ]
        read_only_fields = [f for f in fields if f != 'estado']
