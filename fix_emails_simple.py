#!/usr/bin/env python3
"""
Script simple para corregir emails con usage_count = 2 y status = 'active'
Ejecutar en el servidor: python fix_emails_simple.py
"""

import sqlite3
import os

def fix_emails():
    # Ruta a la base de datos (ajusta según tu configuración)
    db_path = 'app/database/users.db'
    
    if not os.path.exists(db_path):
        print(f"❌ No se encontró la base de datos en: {db_path}")
        return
    
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
