from rest_framework import serializers
from .models import Province, City, Koperasi


class ProvinceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Province
        fields = ["province_id", "province_name"]


class CitySerializer(serializers.ModelSerializer):
    class Meta:
        model = City
        fields = ["city_id", "city_name"]


class KoperasiSerializer(serializers.ModelSerializer):
    class Meta:
        model = Koperasi
        fields = ["koperasi_id", "koperasi_name", "address"]
