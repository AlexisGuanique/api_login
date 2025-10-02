#!/usr/bin/env python3
"""
Script para importar cuentas desde un archivo .txt usando la API local
Formato esperado: User-Agent | Email | Password | Cookie
"""

import os
import sys
import json
import requests
from datetime import datetime

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

def import_accounts_via_api(file_path, user_id, access_token, api_url="http://localhost:8080"):
    """
    Importa cuentas usando la API
    """
    if not os.path.exists(file_path):
        print(f"❌ Error: El archivo {file_path} no existe")
        return False
    
    print(f"📁 Leyendo archivo: {file_path}")
    print(f"👤 Usuario ID: {user_id}")
    print(f"🌐 API URL: {api_url}")
    print("-" * 50)
    
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
    
    # Confirmar importación
    print(f"\n❓ ¿Deseas importar {len(accounts_to_import)} cuentas? (y/N): ", end="")
    response = input().strip().lower()
    
    if response not in ['y', 'yes', 'sí', 'si']:
        print("❌ Importación cancelada")
        return False
    
    # Importar cuentas usando la API
    print("\n🔄 Importando cuentas vía API...")
    
    try:
        # Preparar datos para la API
        api_data = {
            "access_token": access_token,
            "accounts": accounts_to_import
        }
        
        # Enviar petición a la API
        response = requests.post(
            f"{api_url}/api/accounts/save/{user_id}",
            json=api_data,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code in [200, 201]:
            result = response.json()
            print(f"\n🎉 ¡Importación completada!")
            print(f"   Mensaje: {result.get('message', 'Sin mensaje')}")
            print(f"   Cuentas guardadas: {result.get('saved_count', 0)}")
            print(f"   Duplicadas: {result.get('duplicate_count', 0)}")
            print(f"   Total procesadas: {result.get('total_processed', 0)}")
            
            if result.get('duplicate_emails'):
                print(f"   Emails duplicados: {', '.join(result['duplicate_emails'])}")
            
            return True
        else:
            print(f"❌ Error en la API: {response.status_code}")
            try:
                error_data = response.json()
                print(f"   Detalle: {error_data.get('error', 'Error desconocido')}")
            except:
                print(f"   Respuesta: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error durante la importación: {str(e)}")
        return False

def main():
    """
    Función principal del script
    """
    print("🚀 Script de Importación de Cuentas vía API")
    print("=" * 50)
    
    # Verificar argumentos
    if len(sys.argv) < 2:
        print("❌ Uso incorrecto")
        print("📖 Uso: python import_accounts_simple.py <archivo.txt> [api_url]")
        print("📝 Ejemplo: python import_accounts_simple.py accounts.txt http://localhost:8080")
        print("\n📋 Formato del archivo:")
        print("   User-Agent | Email | Password | Cookie")
        print("   # Líneas que empiecen con # son comentarios")
        print("   # Líneas vacías son ignoradas")
        sys.exit(1)
    
    file_path = sys.argv[1]
    api_url = sys.argv[2] if len(sys.argv) > 2 else "http://localhost:8080"
    
    # Configuración fija
    user_id = 2
    access_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VybmFtZSI6ImFkbWluIiwiZXhwIjoxNzYxOTQyODI2fQ.Wps77E7VnL2GXiDXGfSvW2az8Fb19JPPg4uHMnHUapc"
    
    print(f"🔐 Usuario ID: {user_id}")
    print(f"🌐 API: {api_url}")
    
    # Importar cuentas
    success = import_accounts_via_api(file_path, user_id, access_token, api_url)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
