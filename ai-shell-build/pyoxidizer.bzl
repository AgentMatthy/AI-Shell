# PyOxidizer configuration for AI-Shell
# Builds a self-contained executable with embedded Python

def make_exe():
    # Use the default Python distribution
    dist = default_python_distribution()

    # Configure packaging policy
    policy = dist.make_python_packaging_policy()
    
    # Use filesystem-relative mode for best compatibility with terminal libs
    policy.resources_location = "filesystem-relative:lib"
    
    # Include all extension modules
    policy.extension_module_filter = "all"
    
    # Include all resources
    policy.include_distribution_sources = True
    policy.include_distribution_resources = True
    policy.include_non_distribution_sources = True
    policy.allow_files = True
    policy.file_scanner_emit_files = True
    policy.include_file_resources = True

    # Configure Python interpreter
    python_config = dist.make_python_interpreter_config()
    
    # Run our module as the entry point
    python_config.run_module = "ai_shell.main"
    
    # Enable filesystem importer for compatibility
    python_config.filesystem_importer = True
    
    # Set sys.frozen for compatibility detection
    python_config.sys_frozen = True

    # Create the executable
    exe = dist.to_python_executable(
        name="ai-shell",
        packaging_policy=policy,
        config=python_config,
    )

    # Install dependencies via pip
    exe.add_python_resources(exe.pip_install([
        "openai>=1.0.0",
        "pyyaml>=6.0",
        "rich>=13.0.0",
        "tavily-python>=0.3.0",
        "requests>=2.25.0",
        "prompt_toolkit>=3.0.0",
    ]))

    # Add the ai_shell package from source
    exe.add_python_resources(exe.read_package_root(
        path="../src",
        packages=["ai_shell"],
    ))

    return exe

def make_embedded_resources(exe):
    return exe.to_embedded_resources()

def make_install(exe):
    files = FileManifest()
    files.add_python_resource(".", exe)
    return files

register_target("exe", make_exe)
register_target("resources", make_embedded_resources, depends=["exe"])
register_target("install", make_install, depends=["exe"], default_build_script=True)

resolve_targets()
