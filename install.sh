#!/usr/bin/env bash
set -e

INSTALL_DIR="$HOME/.local/share/Bass-Music"
BIN_DIR="$HOME/.local/bin"

echo "🎵 Iniciando instalación de Bass Music..."

# 1. Instalar dependencias del sistema (Linux y macOS)
echo "📦 Verificando dependencias del sistema (mpv)..."
if command -v pacman &> /dev/null; then
    sudo pacman -S --noconfirm --needed mpv
elif command -v apt &> /dev/null; then
    sudo apt update && sudo apt install -y mpv
elif command -v brew &> /dev/null; then
    brew install mpv
else
    echo "⚠️  No se detectó pacman, apt ni brew. Por favor, instala 'mpv' manualmente."
fi

# 2. Copiar repositorio al directorio de instalación
echo "📥 Instalando Bass Music en $INSTALL_DIR..."
mkdir -p "$INSTALL_DIR"
cp -r ./* "$INSTALL_DIR/" 2>/dev/null || true

cd "$INSTALL_DIR"

# 3. Entorno virtual de Python
echo "🐍 Configurando entorno virtual y librerías..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
pip install yt-dlp --quiet

# 4. Crear el comando global 'bass'
echo "🔗 Creando comando global 'bass'..."
mkdir -p "$BIN_DIR"

cat << 'RUNNER' > "$BIN_DIR/bass"
#!/usr/bin/env bash
INSTALL_DIR="$HOME/.local/share/Bass-Music"

if [ "$1" == "--uninstall" ]; then
    echo "🗑️  Desinstalando Bass Music..."
    rm -rf "$INSTALL_DIR"
    rm -f "$HOME/.local/bin/bass"
    echo "✅ ¡Desinstalado por completo!"
    exit 0
fi

exec "$INSTALL_DIR/venv/bin/python" "$INSTALL_DIR/bass.py" "$@"
RUNNER

chmod +x "$BIN_DIR/bass"

if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    echo "⚠️  NOTA: $BIN_DIR no está en tu PATH."
    echo "Agregá esto a tu ~/.bashrc o ~/.zshrc:"
    echo "export PATH=\"\$HOME/.local/bin:\$PATH\""
fi

echo ""
echo "✅ ¡Instalación completada con éxito!"
echo "🎉 Ya podés usar el reproductor escribiendo 'bass' en cualquier terminal."
