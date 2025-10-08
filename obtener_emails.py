#!/usr/bin/env python3
"""
Script simple para obtener emails usando el endpoint de accounts
y guardarlos en un archivo .txt
"""

import requests
import json
import os
from datetime import datetime

# Configuración hardcodeada
API_BASE_URL = "http://35.209.237.44"
EMAILS_ENDPOINT = f"{API_BASE_URL}/api/emails/next/3"
ACCESS_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VybmFtZSI6ImFkbWluIiwiZXhwIjoxNzYxOTM3MDkzfQ.bJIMvIOd-774KfZPLfb6HI6nzuxpt86pjaoKmUuJ_f0"
COUNT = 5

# Archivo de salida
OUTPUT_FILE = "emails_obtenidos.txt"

def obtener_emails():
    """
    Obtiene emails usando el endpoint de accounts
    """
    data = {
        "access_token": ACCESS_TOKEN,
        "count": COUNT
    }
    
    try:
        response = requests.post(EMAILS_ENDPOINT, json=data)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"❌ Error al obtener emails: {e}")
        return None

def guardar_emails_en_archivo(emails, archivo):
    """
    Guarda solo los emails en el archivo .txt
    """
    with open(archivo, "a", encoding="utf-8") as f:
        for email in emails:
            f.write(f"{email['email']}\n")
            print(f"✅ Email guardado: {email['email']}")

def main():
    """
    Función principal del script
    """
    print("🚀 Obteniendo emails...")
    
    # Limpiar archivo de salida si existe
    if os.path.exists(OUTPUT_FILE):
        os.remove(OUTPUT_FILE)
        print(f"🗑️  Archivo anterior eliminado")
    
    # Crear archivo de salida vacío
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        pass
    
    total_emails = 0
    
    while True:
        # Obtener emails
        response_data = obtener_emails()
        
        if not response_data:
            print("❌ No se pudo obtener respuesta del servidor")
            break
        
        emails = response_data.get("emails", [])
        count_obtenidos = len(emails)
        
        if count_obtenidos == 0:
            print("✅ No hay más emails disponibles")
            break
        
        print(f"📨 Se obtuvieron {count_obtenidos} emails")
        
        # Guardar emails en el archivo
        guardar_emails_en_archivo(emails, OUTPUT_FILE)
        
        total_emails += count_obtenidos
        
        # Si obtuvimos menos emails de los solicitados, significa que no hay más
        if count_obtenidos < COUNT:
            print("✅ Se han obtenido todos los emails disponibles")
            break
    
    # Resumen final
    print(f"\n🎉 Proceso completado!")
    print(f"📊 Total de emails obtenidos: {total_emails}")
    print(f"📁 Archivo generado: {OUTPUT_FILE}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Proceso interrumpido por el usuario")
    except Exception as e:
        print(f"\n❌ Error inesperado: {e}")
