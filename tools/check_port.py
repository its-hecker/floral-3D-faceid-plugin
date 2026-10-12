#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Validate the native ABI bindings and installed names of the packaged Face ID port."""
from pathlib import Path
import re
from fetch_prebuilts import ROOT, verify_all
from keymaster_elf import Elf


def check(root=ROOT):
    verify_all(root)
    vendor = root / "proprietary/vendor"
    face = Elf((vendor / "bin/hw/android.hardware.biometrics.face@1.0-service.google").read_bytes())
    expected = {"libcamera2ndk_face.so", "libbase-v33.so", "libstagefright_foundation-v33.so"}
    if not expected <= set(face.needed()) or "libcamera2ndk_vendor.so" in face.needed():
        raise ValueError("Face HAL must use the isolated legacy camera and callback ABI")
    service = Elf((vendor / "bin/hw/android.hardware.keymaster@4.1-service.citadel").read_bytes())
    impl = Elf((vendor / "lib64/android.hardware.keymaster@4.1-impl.nos.so").read_bytes())
    if service.needed()[0] != "libcrypto-v33.so":
        raise ValueError("Citadel must load v33 crypto first")
    if "libcrypto-v33.so" not in impl.needed() or {"libcrypto.so", "libcrypto_shim.so"} & set(impl.needed()):
        raise ValueError("Citadel implementation still uses incompatible crypto")
    crypto = Elf((root / "proprietary/compat/libcrypto-v33.so").read_bytes())
    symbols = re.compile(r"^(?:BN_|EC_|EVP_|RSA_|CBB_|CBS_|OPENSSL_|CRYPTO_|SHA|HMAC_)")
    imports = {n for n, i, *_ in impl.symbols() if not i and symbols.match(n)}
    exports = {n for n, i, *_ in crypto.symbols() if i}
    if not imports or imports - exports:
        raise ValueError("Missing v33 crypto imports: " + str(sorted(imports - exports)))
    calibration = Elf((vendor / "lib64/libautocalsolvers.so").read_bytes())
    if "Autocalibrate" not in {n for n, i, *_ in calibration.symbols() if i}:
        raise ValueError("Face calibration entry point missing")
    source = (root / "native/camera/compat/AHandler.h").read_text()
    if "sizeof(android::AHandler) == 96" not in source:
        raise ValueError("Legacy callback layout assertion missing")
    bp = (root / "Android.bp.in").read_text()
    for name in ["FloralFaceIDHal", "FloralFaceIDCitadelKeymaster", "FloralFaceIDAutocalSolvers"]:
        if 'name: "' + name + '"' not in bp:
            raise ValueError("Missing native module: " + name)
    rc = (root / "configs/floral-faceid-citadel.rc").read_text()
    if "LD_PRELOAD" in rc or "    user hsm\n" not in rc or "    group hsm drmrpc\n" not in rc:
        raise ValueError("Citadel identity or explicit crypto loading changed")
    print("Face camera/callback ABI, calibration and Citadel crypto imports: PASS")
    print("Crypto symbols supplied:", len(imports))
    print("All native inputs match immutable checksums; no authentication code patched")


if __name__ == "__main__":
    check()
