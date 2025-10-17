#!/usr/bin/env python3
"""
Script para corregir emails con usage_count = 2 y status = 'active' en Docker
Ejecutar dentro del contenedor Docker
"""

import sqlite3
import os
import sys

def fix_emails():
    # En Docker, la base de datos debería estar en /app/database/users.db
    db_path = '/app/database/users.db'
    
    print(f"🔍 Buscando base de datos en: {db_path}")
    
    if not os.path.exists(db_path):
        print(f"❌ No se encontró la base de datos en: {db_path}")
        print("\n🔍 Buscando archivos .db en el contenedor...")
        
        # Buscar archivos .db en el contenedor
        for root, dirs, files in os.walk('/app'):
            for file in files:
                if file.endswith('.db'):
                    full_path = os.path.join(root, file)
                    print(f"   - {full_path}")
        
        return
    
    print(f"✅ Base de datos encontrada en: {db_path}")
    
    try:
        # Conectar a la base de datos
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("🔍 Verificando emails con usage_count = 2 y status = 'active'...")
        
        # Contar emails que necesitan corrección
        cursor.execute("""
            SELECT COUNT(*) 
            FROM email 
            WHERE usage_count = 2 AND status = 'active'
        """)
        
        emails_to_fix = cursor.fetchone()[0]
        print(f"📊 Se encontraron {emails_to_fix} emails que necesitan corrección")
        
        if emails_to_fix == 0:
            print("✅ No hay emails que corregir. Todo está bien.")
            return
        
        # Mostrar estadísticas antes
        print("\n📈 Estadísticas ANTES:")
        cursor.execute("""
            SELECT status, usage_count, COUNT(*) as count
            FROM email 
            GROUP BY status, usage_count
            ORDER BY status, usage_count
        """)
        
        for row in cursor.fetchall():
            print(f"  Status: {row[0]}, Usage Count: {row[1]}, Count: {row[2]}")
        
        # Actualizar emails
        print(f"\n🔄 Actualizando {emails_to_fix} emails...")
        cursor.execute("""
            UPDATE email 
            SET status = 'completed' 
            WHERE usage_count = 2 AND status = 'active'
        """)
        
        updated_count = cursor.rowcount
        conn.commit()
        
        print(f"✅ Se actualizaron {updated_count} emails exitosamente")
        
        # Mostrar estadísticas después
        print("\n📈 Estadísticas DESPUÉS:")
        cursor.execute("""
            SELECT status, usage_count, COUNT(*) as count
            FROM email 
            GROUP BY status, usage_count
            ORDER BY status, usage_count
        """)
        
        for row in cursor.fetchall():
            print(f"  Status: {row[0]}, Usage Count: {row[1]}, Count: {row[2]}")
        
        # Verificar corrección
        cursor.execute("""
            SELECT COUNT(*) 
            FROM email 
            WHERE usage_count = 2 AND status = 'active'
        """)
        
        remaining = cursor.fetchone()[0]
        
        if remaining == 0:
            print("\n🎉 ¡Corrección completada exitosamente!")
        else:
            print(f"\n⚠️  Aún quedan {remaining} emails incorrectos.")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    print("🚀 Corrigiendo status de emails en Docker...")
    fix_emails()
    print("✨ Completado.")
