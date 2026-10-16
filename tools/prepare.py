#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Prepare namespaced native modules and a face overlay for an Android 17 Floral tree."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

from fetch_prebuilts import ROOT, verify_all
from apply_framework_fixes import apply as check_framework


def sensor_config(paths, requested_id=None):
    selected = []
    for path in paths:
        arrays = [n for n in ET.parse(path).getroot() if n.get("name") == "config_biometric_sensors"]
        if len(arrays) > 1:
            raise ValueError("Duplicate biometric sensor config in " + str(path))
        if arrays:
            selected = [(n.text or "").strip() for n in arrays[0]]
    sensors = []
    for value in selected:
        if not re.fullmatch(r"\d+:\d+:\d+", value):
            raise ValueError("Unexpected biometric sensor entry: " + value)
        sensors.append(tuple(int(v) for v in value.split(":")))
    ids = [v[0] for v in sensors]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate biometric sensor IDs in active overlay")
    faces = [v for v in sensors if v[1] == 8]
    if len(faces) > 1:
        raise ValueError("Multiple face sensors need explicit provider integration")
    if faces:
        if faces[0][2] != 15:
            raise ValueError("Existing face strength differs; review it before replacing its provider")
        if requested_id is not None and faces[0][0] != requested_id:
            raise ValueError("Requested face ID conflicts with the existing face configuration")
        face_id = faces[0][0]
    else:
        face_id = requested_id if requested_id is not None else next(i for i in range(len(ids) + 1) if i not in ids)
        if face_id in ids or face_id < 0:
            raise ValueError("Face sensor ID must be unused and nonnegative")
        selected.append(f"{face_id}:8:15")
    return selected, face_id


def namespace_imports(vendor, rom):
    source = (vendor / "Android.bp").read_text()
    imports = []
    if re.search(r"^soong_namespace\s*\{", source, re.M):
        imports.append(vendor.relative_to(rom).as_posix())
        block = re.search(r"soong_namespace\s*\{(.*?)\n\}", source, re.S).group(1)
        value = re.search(r"imports\s*:\s*\[(.*?)\]", block, re.S)
        if value:
            imports.extend(re.findall(r'"([^"]+)"', value.group(1)))
    return list(dict.fromkeys(imports))


def foundation_module(rom, root):
    # Reuse Lineage's identical multilib provider instead of overriding its
    # whole module with our arm64-only fallback and dropping its arm variant.
    module = "libstagefright_foundation-v33"
    source = rom / "hardware/lineage/compat/Android.bp"
    if not source.is_file():
        return "FloralFaceIDV33Foundation", []
    text = source.read_text()
    if not re.search(r'\bname:\s*"' + module + r'"', text):
        return "FloralFaceIDV33Foundation", [source]
    block = re.search(r'(?ms)^cc_prebuilt_library_shared\s*\{\s*name:\s*"' +
                      module + r'",.*?^\}', text)
    if (not block or 'vendor_available: true' not in block.group() or
            '"vndk/v33/arm64/' + module + '.so"' not in block.group()):
        raise ValueError("Review the existing v33 foundation provider before sharing it")
    binary = source.parent / "vndk/v33/arm64" / (module + ".so")
    if binary.read_bytes() != (root / "proprietary/compat" / (module + ".so")).read_bytes():
        raise ValueError("Existing v33 foundation differs from the pinned Face ID ABI")
    return module, [source, binary]


def prepare(rom, vendor, overlays, requested_id=None, skip_vintf=False, root=ROOT):
    verify_all(root)
    status, _ = check_framework(rom, write=False)
    if status == "patch available":
        raise ValueError("Apply tools/apply_framework_fixes.py --rom-root <ROM> --apply first")
    imports = namespace_imports(vendor, rom)
    foundation, foundation_inputs = foundation_module(rom, root)
    sensors, face_id = sensor_config(overlays, requested_id)
    # This userspace port relies on the real Floral hardware/firmware base.
    for file in ["proprietary/vendor/firmware/faceauth_config.yaml",
                 "proprietary/vendor/firmware/faceauth_v1.mdt"]:
        if not (vendor / file).is_file():
            raise ValueError("Base Floral vendor firmware missing: " + file)
    for path in ["Android.bp", "native/camera/Android.bp"]:
        target = root / path
        text = target.with_suffix(".bp.in").read_text()
        text = text.replace("@NAMESPACE_IMPORTS@", json.dumps(imports))
        if foundation != "FloralFaceIDV33Foundation":
            text = re.sub(r'(?ms)^cc_prebuilt_library_shared\s*\{\s*name:\s*'
                          r'"FloralFaceIDV33Foundation",.*?^\}\n?', '', text)
            text = text.replace('"FloralFaceIDV33Foundation"', '"' + foundation + '"')
        target.write_text(text)
    generated = root / "generated"
    generated.mkdir(exist_ok=True)
    (generated / "profile.mk").write_text(
        "FLORAL_FACEID_ADD_VINTF := " + str(not skip_vintf).lower() + "\n" +
        "FLORAL_FACEID_FOUNDATION_MODULE := " + foundation + "\n")
    config = ET.Element("resources")
    array = ET.SubElement(config, "string-array", name="config_biometric_sensors", translatable="false")
    for value in sensors:
        ET.SubElement(array, "item").text = value
    # Keep the tested Pixel acquisition guidance without changing authenticator checks.
    for name, values in {
        "config_face_acquire_enroll_ignorelist": [13],
        "config_face_acquire_biometricprompt_ignorelist": [1,2,3,4,5,6,7,8,9,11,12,13,14,15,16,17,18,19],
        "config_face_acquire_keyguard_ignorelist": [1,2,3,4,5,11,12,13,14,15,19],
    }.items():
        item = ET.SubElement(config, "integer-array", name=name)
        for value in values:
            ET.SubElement(item, "item").text = str(value)
    ET.indent(config, space="    ")
    path = root / "overlay/res/values/config.xml"
    path.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(config).write(path, encoding="utf-8", xml_declaration=True)
    with (root / "Android.bp").open("a") as output:
        output.write('''
runtime_resource_overlay {
    name: "FloralFaceIDFrameworkOverlay",
    manifest: "overlay/AndroidManifest.xml",
    resource_dirs: ["overlay/res"],
    sdk_version: "current",
    certificate: "platform",
    system_ext_specific: true,
}
''')
    outputs = ["Android.bp", "native/camera/Android.bp", "overlay/res/values/config.xml", "generated/profile.mk"]
    inputs = list(dict.fromkeys(overlays + [vendor / "Android.bp"] + foundation_inputs))
    profile = {"vendor_namespace_imports": imports, "sensors": sensors,
               "foundation_module": foundation,
               "face_sensor_id": face_id, "add_vintf": not skip_vintf,
               "input_files": [{"path": str(p.resolve()), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in inputs],
               "output_files": [{"path": p, "sha256": hashlib.sha256((root/p).read_bytes()).hexdigest()} for p in outputs]}
    (generated / "profile.json").write_text(json.dumps(profile, indent=2) + "\n")
    print("Face ID plugin prepared; hardware face sensor ID:", face_id)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom-root", type=Path, default=Path.cwd())
    parser.add_argument("--vendor-tree", type=Path, required=True)
    parser.add_argument("--biometrics-xml", type=Path, action="append", default=[],
                        help="Active framework overlays, lowest to highest priority")
    parser.add_argument("--face-sensor-id", type=int)
    parser.add_argument("--skip-face-vintf", action="store_true",
                        help="Keep an existing IBiometricsFace/default entry outside the replaced stock module")
    args = parser.parse_args()
    try:
        rom = args.rom_root.resolve()
        def absolute(path): return path if path.is_absolute() else rom / path
        vendor = absolute(args.vendor_tree).resolve()
        overlays = [rom / "frameworks/base/core/res/res/values/config.xml"]
        overlays += [absolute(p) for p in args.biometrics_xml]
        prepare(rom, vendor, overlays, args.face_sensor_id, args.skip_face_vintf)
    except (OSError, ValueError, ET.ParseError) as error:
        print("Face ID setup:", error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
