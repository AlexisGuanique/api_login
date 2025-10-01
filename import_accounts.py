#!/usr/bin/env python3
"""
Script para importar cuentas desde un archivo .txt a la base de datos
Formato esperado: User-Agent | Email | Password | Cookie
"""

import os
import sys
import json
from datetime import datetime
from app import create_app
from app.models.account import Account
from app.models.user import User
from app.database import db

def parse_account_line(line, line_number):
    """
    Parsea una línea del archivo con formato: User-Agent | Email | Password | Cookie
    También acepta separación por tabulaciones
    """
    line = line.strip()
    if not line or line.startswith('#'):
        return None
    
    # Intentar dividir por | primero, luego por tabulaciones
    if '|' in line:
        parts = line.split('|')
    elif '\t' in line:
        parts = line.split('\t')
    else:
        print(f"❌ Línea {line_number}: Formato incorrecto. Esperado: User-Agent | Email | Password | Cookie (o separado por tabs)")
        return None
    
    if len(parts) != 4:
        print(f"❌ Línea {line_number}: Formato incorrecto. Esperado: User-Agent | Email | Password | Cookie")
        return None
    
    user_agent = parts[0].strip()
    email = parts[1].strip()
    password = parts[2].strip()
    cookie = parts[3].strip()
    
    # Validaciones básicas
    if not user_agent or not email or not password or not cookie:
        print(f"❌ Línea {line_number}: Campos vacíos detectados")
        return None
    
    if '@' not in email:
        print(f"❌ Línea {line_number}: Email inválido: {email}")
        return None
    
    return {
        'user_agent': user_agent,
        'email': email,
        'password': password,
        'cookie': cookie
    }

def import_accounts_from_file(file_path, user_id):
    """
    Importa cuentas desde un archivo .txt
    """
    if not os.path.exists(file_path):
        print(f"❌ Error: El archivo {file_path} no existe")
        return False
    
    print(f"📁 Leyendo archivo: {file_path}")
    print(f"👤 Usuario ID: {user_id}")
    print("-" * 50)
    
    # Verificar que el usuario existe
    user = User.query.get(user_id)
    if not user:
        print(f"❌ Error: Usuario con ID {user_id} no encontrado")
        return False
    
    print(f"✅ Usuario encontrado: {user.username}")
    
    # Leer y procesar el archivo
    accounts_to_import = []
    line_number = 0
    
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            for line in file:
                line_number += 1
                account_data = parse_account_line(line, line_number)
                if account_data:
                    accounts_to_import.append(account_data)
                    print(f"✅ Línea {line_number}: {account_data['email']}")
                else:
                    print(f"⏭️  Línea {line_number}: Saltada")
    
    except Exception as e:
        print(f"❌ Error leyendo archivo: {str(e)}")
        return False
    
    if not accounts_to_import:
        print("❌ No se encontraron cuentas válidas para importar")
        return False
    
    print(f"\n📊 Resumen:")
    print(f"   Total de líneas procesadas: {line_number}")
    print(f"   Cuentas válidas encontradas: {len(accounts_to_import)}")
    
    # Verificar duplicados
    emails = [acc['email'] for acc in accounts_to_import]
    existing_accounts = Account.query.filter(
        Account.email.in_(emails),
        Account.user_id == user_id
    ).all()
    
    existing_emails = [acc.email for acc in existing_accounts]
    new_accounts = [acc for acc in accounts_to_import if acc['email'] not in existing_emails]
    
    print(f"   Cuentas ya existentes: {len(existing_emails)}")
    print(f"   Cuentas nuevas a importar: {len(new_accounts)}")
    
    if existing_emails:
        print(f"   Emails duplicados: {', '.join(existing_emails)}")
    
    if not new_accounts:
        print("ℹ️  No hay cuentas nuevas para importar")
        return True
    
    # Confirmar importación
    print(f"\n❓ ¿Deseas importar {len(new_accounts)} cuentas? (y/N): ", end="")
    response = input().strip().lower()
    
    if response not in ['y', 'yes', 'sí', 'si']:
        print("❌ Importación cancelada")
        return False
    
    # Importar cuentas
    print("\n🔄 Importando cuentas...")
    imported_count = 0
    
    try:
        for account_data in new_accounts:
            new_account = Account(
                user_agent=account_data['user_agent'],
                email=account_data['email'],
                password=account_data['password'],
                cookie=account_data['cookie'],
                user_id=user_id
            )
            db.session.add(new_account)
            imported_count += 1
            print(f"   ✅ {account_data['email']}")
        
        db.session.commit()
        print(f"\n🎉 ¡Importación completada!")
        print(f"   Cuentas importadas: {imported_count}")
        print(f"   Usuario: {user.username} (ID: {user_id})")
        
        return True
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error durante la importación: {str(e)}")
        return False

def main():
    """
    Función principal del script
    """
    print("🚀 Script de Importación de Cuentas")
    print("=" * 50)
    
    # Verificar argumentos
    if len(sys.argv) != 3:
        print("❌ Uso incorrecto")
        print("📖 Uso: python import_accounts.py <archivo.txt> <user_id>")
        print("📝 Ejemplo: python import_accounts.py accounts.txt 1")
        print("\n📋 Formato del archivo:")
        print("   User-Agent | Email | Password | Cookie")
        print("   # Líneas que empiecen con # son comentarios")
        print("   # Líneas vacías son ignoradas")
        sys.exit(1)
    
    file_path = sys.argv[1]
    try:
        user_id = int(sys.argv[2])
    except ValueError:
        print("❌ Error: user_id debe ser un número entero")
        sys.exit(1)
    
    # Configurar ruta absoluta de la base de datos antes de crear la app
    import os
    database_path = os.path.abspath('app/database')
    os.environ['DATABASE_PATH'] = database_path
    
    # Crear aplicación Flask
    app = create_app()
    
    with app.app_context():
        success = import_accounts_from_file(file_path, user_id)
        sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
