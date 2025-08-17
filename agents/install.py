import subprocess

def install_package(package_name):
    """
    Installs a package using the system's package manager.
    """
    try:
        # Attempt to install using apt
        subprocess.run(["sudo", "apt", "install", "-y", package_name], check=True)
        return f"Successfully installed {package_name}"
    except subprocess.CalledProcessError:
        try:
            # Attempt to install using pacman
            subprocess.run(["sudo", "pacman", "-S", "--noconfirm", package_name], check=True)
            return f"Successfully installed {package_name}"
        except subprocess.CalledProcessError:
            return f"Failed to install {package_name}. Please check your package manager."

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        print(install_package(sys.argv[1]))
