"""
Stockfish Auto-Download Script for ChessGenie.

Downloads and sets up Stockfish chess engine automatically.
Run with: python download_stockfish.py
"""
import os
import sys
import platform
import zipfile
import httpx
import shutil
from pathlib import Path

# Stockfish download URLs (official releases)
STOCKFISH_URLS = {
    "Windows": "https://github.com/official-stockfish/Stockfish/releases/download/sf_17.1/stockfish-windows-x86-64-avx2.zip",
    "Linux": "https://github.com/official-stockfish/Stockfish/releases/download/sf_17.1/stockfish-ubuntu-x86-64-avx2.tar",
    "Darwin": "https://github.com/official-stockfish/Stockfish/releases/download/sf_17.1/stockfish-macos-m1-apple-silicon.tar",
}

ENGINES_DIR = Path(__file__).parent / "engines"


def get_stockfish_path() -> Path:
    """Get the expected path to the Stockfish executable."""
    system = platform.system()
    
    if system == "Windows":
        return ENGINES_DIR / "stockfish-windows-x86-64-avx2.exe"
    elif system == "Linux":
        return ENGINES_DIR / "stockfish-ubuntu-x86-64-avx2"
    elif system == "Darwin":
        return ENGINES_DIR / "stockfish-macos-m1-apple-silicon"
    else:
        raise RuntimeError(f"Unsupported platform: {system}")


def is_stockfish_installed() -> bool:
    """Check if Stockfish is already downloaded."""
    stockfish_path = get_stockfish_path()
    return stockfish_path.exists()


def download_stockfish() -> Path:
    """Download and extract Stockfish for the current platform."""
    system = platform.system()
    
    if system not in STOCKFISH_URLS:
        raise RuntimeError(f"Unsupported platform: {system}. Please download Stockfish manually from stockfishchess.org")
    
    url = STOCKFISH_URLS[system]
    print(f"📥 Downloading Stockfish for {system}...")
    print(f"   URL: {url}")
    
    # Create engines directory
    ENGINES_DIR.mkdir(parents=True, exist_ok=True)
    
    # Download the file
    archive_name = url.split("/")[-1]
    archive_path = ENGINES_DIR / archive_name
    
    with httpx.Client(follow_redirects=True, timeout=120.0) as client:
        response = client.get(url)
        response.raise_for_status()
        
        with open(archive_path, "wb") as f:
            f.write(response.content)
    
    print(f"✅ Downloaded to {archive_path}")
    
    # Extract the archive
    print("📦 Extracting...")
    
    if archive_name.endswith(".zip"):
        with zipfile.ZipFile(archive_path, 'r') as zip_ref:
            zip_ref.extractall(ENGINES_DIR)
    elif archive_name.endswith(".tar"):
        import tarfile
        with tarfile.open(archive_path, 'r') as tar_ref:
            tar_ref.extractall(ENGINES_DIR)
    
    # Find and move the executable
    stockfish_exe = None
    for root, dirs, files in os.walk(ENGINES_DIR):
        for file in files:
            if file.startswith("stockfish") and not file.endswith((".zip", ".tar")):
                stockfish_exe = Path(root) / file
                break
    
    if stockfish_exe and stockfish_exe.parent != ENGINES_DIR:
        # Move to engines root
        dest = ENGINES_DIR / stockfish_exe.name
        shutil.move(str(stockfish_exe), str(dest))
        stockfish_exe = dest
    
    # Clean up archive and extracted directories
    archive_path.unlink(missing_ok=True)
    for item in ENGINES_DIR.iterdir():
        if item.is_dir():
            shutil.rmtree(item)
    
    # Make executable on Unix
    if system != "Windows" and stockfish_exe:
        stockfish_exe.chmod(0o755)
    
    print(f"✅ Stockfish installed at: {stockfish_exe}")
    return stockfish_exe


def verify_stockfish() -> bool:
    """Verify Stockfish works by running a simple command."""
    import subprocess
    
    stockfish_path = get_stockfish_path()
    if not stockfish_path.exists():
        return False
    
    try:
        # Run Stockfish and send 'uci' command
        process = subprocess.Popen(
            [str(stockfish_path)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = process.communicate(input="uci\nquit\n", timeout=5)
        
        if "uciok" in stdout:
            print("✅ Stockfish verification successful!")
            return True
        else:
            print(f"❌ Stockfish verification failed: {stderr}")
            return False
    except Exception as e:
        print(f"❌ Stockfish verification failed: {e}")
        return False


def main():
    """Main entry point."""
    print("=" * 50)
    print("ChessGenie Stockfish Setup")
    print("=" * 50)
    print()
    
    if is_stockfish_installed():
        stockfish_path = get_stockfish_path()
        print(f"✅ Stockfish already installed at: {stockfish_path}")
    else:
        print("Stockfish not found. Downloading...")
        try:
            download_stockfish()
        except Exception as e:
            print(f"❌ Download failed: {e}")
            print("\nPlease download manually from: https://stockfishchess.org/download/")
            sys.exit(1)
    
    print()
    print("Verifying installation...")
    if verify_stockfish():
        print()
        print("=" * 50)
        print("🎉 Stockfish is ready for ChessGenie!")
        print("=" * 50)
    else:
        print()
        print("⚠️  Stockfish installed but verification failed.")
        print("You may need to download a different version for your CPU.")
        sys.exit(1)


if __name__ == "__main__":
    main()
