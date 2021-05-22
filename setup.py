from setuptools import setup
from setuptools_rust import RustExtension

setup(
    name="image-hash",
    version="1.0",
    rust_extensions=[RustExtension("image_hash.image_hash", "Cargo.toml", debug=False)],
    packages=["image_hash"],
    include_package_data=True,
    zip_safe=False
)
