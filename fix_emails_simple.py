#!/usr/bin/env python3
"""
Script simple para corregir emails con usage_count = 2 y status = 'active'
Ejecutar en el servidor: python fix_emails_simple.py
"""

import sqlite3
import os

def fix_emails():
    # Posibles rutas de la base de datos
    possible_paths = [
        'app/database/users.db',
        'database/users.db',
        'users.db',
        'instance/users.db',
        'app/users.db'
    ]
    
    db_path = None
    for path in possible_paths:
        if os.path.exists(path):
            db_path = path
            break
    
    if not db_path:
        print("❌ No se encontró la base de datos en ninguna de las ubicaciones:")
        for path in possible_paths:
            print(f"   - {path}")
        print("\n🔍 Buscando archivos .db en el directorio actual...")
        
        # Buscar archivos .db en el directorio actual y subdirectorios
        for root, dirs, files in os.walk('.'):
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

if __name__ == "__main__":
    print("🚀 Corrigiendo status de emails...")
    fix_emails()
    print("✨ Completado.")
