name: Cosechador Historico Valle Hermoso

on:
  schedule:
    # Se ejecuta todos los días a las 00:00 hora de Chile (04:00 AM UTC)
    - cron: '0 4 * * *'
  workflow_dispatch: # Permite ejecución manual

jobs:
  cosechar:
    runs-on: ubuntu-latest

    steps:
    - name: Checkout del repositorio
      uses: actions/checkout@v4

    - name: Configurar Python
      uses: actions/setup-python@v5
      with:
        python-version: '3.10'

    - name: Instalar dependencias
      run: |
        python -m pip install --upgrade pip
        pip install requests pandas gspread google-auth

    - name: Ejecutar script de cosecha
      env:
        ZENTRA_TOKEN: ${{ secrets.ZENTRA_TOKEN }}
        DEVICE_SN: ${{ secrets.DEVICE_SN }}
        GOOGLE_CREDS: ${{ secrets.GOOGLE_CREDS }}
      run: python cosechador.py
