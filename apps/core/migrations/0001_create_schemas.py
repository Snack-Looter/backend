from django.db import migrations


class Migration(migrations.Migration):
    """
    Membuat schema 'kopquest' dan 'kopdes' sebelum app lain membuat tabel
    di dalamnya. Semua app model (accounts, gamification, catalog,
    transactions) harus depend ke migration ini.
    """
    initial = True
    dependencies = []

    operations = [
        migrations.RunSQL(
            sql='CREATE SCHEMA IF NOT EXISTS kopquest; CREATE SCHEMA IF NOT EXISTS kopdes;',
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
