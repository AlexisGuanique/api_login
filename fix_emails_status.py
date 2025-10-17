#!/usr/bin/env python3
"""
Script para corregir emails con usage_count = 2 y status = 'active' a status = 'completed'
Este script debe ejecutarse en el servidor donde está la base de datos.
"""

import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Configuración de la base de datos
# Ajusta estos valores según tu configuración
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///app/database/users.db')

def fix_emails_status():
    """Corregir el status de emails con usage_count = 2"""
    try:
        # Crear conexión a la base de datos
        engine = create_engine(DATABASE_URL)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        print("🔍 Verificando emails con usage_count = 2 y status = 'active'...")
        
        # Contar emails que necesitan corrección
        count_query = text("""
            SELECT COUNT(*) as count
            FROM email 
            WHERE usage_count = 2 AND status = 'active'
        """)
        
        result = session.execute(count_query).fetchone()
        emails_to_fix = result.count if result else 0
        
        print(f"📊 Se encontraron {emails_to_fix} emails que necesitan corrección")
        
        if emails_to_fix == 0:
            print("✅ No hay emails que corregir. Todo está bien.")
            return
        
        # Mostrar estadísticas antes de la corrección
        print("\n📈 Estadísticas ANTES de la corrección:")
        stats_query = text("""
            SELECT 
                status,
                usage_count,
                COUNT(*) as count
            FROM email 
            GROUP BY status, usage_count
            ORDER BY status, usage_count
        """)
        
        stats_result = session.execute(stats_query).fetchall()
        for row in stats_result:
            print(f"  Status: {row.status}, Usage Count: {row.usage_count}, Count: {row.count}")
        
        # Actualizar emails con usage_count = 2 y status = 'active' a status = 'completed'
        print(f"\n🔄 Actualizando {emails_to_fix} emails...")
        
        update_query = text("""
            UPDATE email 
            SET status = 'completed' 
            WHERE usage_count = 2 AND status = 'active'
        """)
        
        result = session.execute(update_query)
        updated_count = result.rowcount
        session.commit()
        
        print(f"✅ Se actualizaron {updated_count} emails exitosamente")
        
        # Mostrar estadísticas después de la corrección
        print("\n📈 Estadísticas DESPUÉS de la corrección:")
        stats_result = session.execute(stats_query).fetchall()
        for row in stats_result:
            print(f"  Status: {row.status}, Usage Count: {row.usage_count}, Count: {row.count}")
        
        # Verificar que no queden emails con usage_count = 2 y status = 'active'
        verify_query = text("""
            SELECT COUNT(*) as count
            FROM email 
            WHERE usage_count = 2 AND status = 'active'
        """)
        
        verify_result = session.execute(verify_query).fetchone()
        remaining_incorrect = verify_result.count if verify_result else 0
        
        if remaining_incorrect == 0:
            print("\n🎉 ¡Corrección completada exitosamente! No quedan emails incorrectos.")
        else:
            print(f"\n⚠️  Advertencia: Aún quedan {remaining_incorrect} emails con status incorrecto.")
        
        session.close()
        
    except Exception as e:
        print(f"❌ Error durante la corrección: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    print("🚀 Iniciando corrección de status de emails...")
    print(f"📡 Conectando a base de datos: {DATABASE_URL}")
    fix_emails_status()
    print("✨ Script completado.")
