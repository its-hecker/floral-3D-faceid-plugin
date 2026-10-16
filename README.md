# Floral 3D Face ID plugin — Android 17

Reusable **hardware 3D Face Unlock** integration for Pixel 4 (`flame`) and
Pixel 4 XL (`coral`). The plugin packages my working Floral Face HAL
compatibility repair as product/board includes, isolated native modules,
guarded framework patches and a generated biometric configuration.

It uses the stock IR/FaceAuth hardware, calibration solver and Citadel-backed
authentication stack. Face enrollment and authentication remain in the ROM's
normal Settings, lock screen and BiometricPrompt. Motion Sense is independent:
[floral-motionsense-plugin](https://github.com/its-hecker/floral-motionsense-plugin).

## What is packaged

- The Google Face HAL with explicit legacy camera/base/callback bindings.
- Source-built Camera NDK compatibility with the checked **96-byte AHandler**
  layout and original HIDL camera interface.
- The stock `Autocalibrate` solver and Face calibration/enrollment libraries.
- Citadel Keymaster with **v33 crypto loaded first**, and its matching NOS
  implementation. The service keeps its `hsm` user and `hsm drmrpc` groups.
- Matching v33 base, crypto and stagefright libraries, plus the tested Airbrush
  and Noronha service bindings.
- Guarded shared-challenge completion and enrollment feature-translation fixes.
- A platform-signed framework overlay that preserves other biometric sensors,
  plus the hardware feature permission, Face VINTF fragment and HAL policy.

Native inputs are pinned by SHA-256 in `prebuilts.lock.json` and downloaded
before building. Native executable/authentication code is retained from the
validated source port. The framework patch preserves token forwarding, native
attention defaults, reduced-pose enrollment and other clients' challenge state.

## Prerequisites

A working Android 17 **Floral** device/vendor/kernel base is required. Keep
the real IR camera provider, Airbrush/Citadel services and interfaces, FaceAuth
firmware, `/dev/faceauth`, and the phone's own persistent calibration. The
plugin supplies userspace compatibility; it does not replace a device tree,
kernel, factory firmware or device-specific calibration.

The base vendor tree must still provide the normal Floral dependencies such as
NOS libraries, Google hardware interfaces, legacy protobuf modules and camera
services. Setup imports that vendor tree's actual Soong namespace/imports,
so it is not tied to `vendor/google/coral` or an Infinity product name.

The guarded patches currently support the known Android 17 HIDL adapter/client
methods. ROM-specific changes are preserved around those methods. An unfamiliar
method is refused and needs review; forcing an unmatched patch is not an
integration step.

## Integration

Run from the ROM checkout root:

```bash
git clone https://github.com/its-hecker/floral-3D-faceid-plugin \
  vendor/hecker/floral/faceid
python3 vendor/hecker/floral/faceid/tools/fetch_prebuilts.py
python3 vendor/hecker/floral/faceid/tools/apply_framework_fixes.py --check
python3 vendor/hecker/floral/faceid/tools/apply_framework_fixes.py --apply
```

The apply command backs up the adapter under `out/face-framework-patches/` and
is idempotent. It verifies the incoming feature builder before writing. Rerun
it after syncing `frameworks/base`.

Prepare the native namespace and the **active** biometric sensor array. The base
framework resource is read automatically; selected device overlays are supplied
in lowest to highest priority order. For the common Coral tree:

```bash
python3 vendor/hecker/floral/faceid/tools/prepare.py \
  --vendor-tree vendor/google/coral \
  --biometrics-xml device/google/coral/overlay/frameworks/base/core/res/res/values/config.xml
```

For Flame or another common-tree layout, use its actual vendor namespace and
active framework overlays. Existing fingerprint entries are retained. If there
is no face row, an unused sensor ID is selected for the hardware Face provider.
An existing weak/software face configuration is refused rather than silently
reclassified. Remove the software provider/configuration before enabling this
hardware provider. `--face-sensor-id N` selects a specific unused ID when needed.

Add to `device.mk` **after** the base device/vendor product inheritance:

```make
$(call inherit-product, vendor/hecker/floral/faceid/faceid.mk)
```

Add to `BoardConfig.mk`:

```make
include vendor/hecker/floral/faceid/BoardConfigFaceID.mk
```

The product replaces the listed older Face/Citadel/Airbrush/Noronha packages and
legacy libraries, keeping the stock installed filenames. It removes the two
older init-copy destinations and installs the guarded service definitions.
Other base hardware packages, properties and policy remain supplied by your tree.
Preserve `+=` for your base VINTF/policy lists.

The replacement Face/Citadel shared libraries declare `overrides` as well as
filtering product entries. Soong's generated vendor image can otherwise pull
the originals back in through another module's dependencies and report two
owners for the same library path. When Lineage's v33 base, crypto or stagefright
providers are present, preparation verifies their arm64 binaries against the
immutable plugin inputs and shares those modules. Their existing 32-bit variants
remain available. Missing providers use the plugin's pinned arm64 fallbacks. A differing
existing binary requires ABI review; preparation stops before generating files.

The stock `manifest_face.xml` module selection is replaced with
`FloralFaceIDManifest`. If an additional device manifest already registers
`IBiometricsFace/default`, remove that duplicate or run preparation with
`--skip-face-vintf` to retain it. There must be one matching hardware provider
instance, rather than both a software face service and this service.

Use the ROM's normal lunch target and build command. Product configuration
verifies the cached binaries, generated inputs and applied framework fixes
before continuing. After a sync or an overlay/vendor namespace change, rerun
the preparation commands.

Optional local manifest:

```xml
<manifest>
    <remote name="hecker" fetch="https://github.com/its-hecker/" />
    <project name="floral-3D-faceid-plugin"
             path="vendor/hecker/floral/faceid"
             remote="hecker" revision="main" />
</manifest>
```

## Verification

Before flashing (replace `coral` with `flame` where appropriate):

```bash
readelf -d out/target/product/coral/vendor/bin/hw/android.hardware.biometrics.face@1.0-service.google
readelf -d out/target/product/coral/vendor/bin/hw/android.hardware.keymaster@4.1-service.citadel
readelf -Ws out/target/product/coral/vendor/lib64/libautocalsolvers.so | rg Autocalibrate
```

Face must bind `libcamera2ndk_face.so`, `libbase-v33.so` and
`libstagefright_foundation-v33.so`. Citadel's first dependency must be
`libcrypto-v33.so`; its NOS implementation must not load modern crypto or the
crypto shim as substitutes. Keep the real HAL/VINTF registration and service
identities.

After flashing, test enrollment, lock-screen authentication, repeated visits
to Face Unlock settings, authentication afterward, model removal/re-enrollment
and a hardware-backed BiometricPrompt operation. Collect failures immediately:

```bash
adb logcat -b all -d > floral-faceid-logcat.txt
adb logcat -b crash -d > floral-faceid-crash.txt
adb shell dumpsys face > floral-faceid-service.txt
adb shell lshal > floral-hal-services.txt
```

IR capture failures point toward camera/firmware/calibration integration;
Citadel crashes require checking the **running** service's crypto mappings;
settings/removal queues stalling require checking that the framework patches
survived the sync. [Framework patch details](patches/README.md) explain the
challenge and pose behavior and their regression harnesses.

## Validation status

| Item | Status |
| --- | --- |
| Source port on Coral / Infinity Android 17 | Enrollment, unlock and challenge-queue recovery confirmed on the phone |
| Plugin inputs and setup | Native ABI/export/checksum checks and sensor-preservation tests in CI |
| Framework fixes | Guarded-source tests and extracted Java challenge/pose regressions in CI |
| Full ROM using this standalone package | Requires builder validation |
| Flame and other Android 17 ROM forks | Integration targets; phone verification still required |

The ROM's existing enrollment UI is retained. Stock Pixel's moving pose boxes
have not been ported. Individual ROMs can modify their Settings UI independently
of this hardware compatibility package.

## Credits and sources

Port, compatibility fixes and packaging: **Hecker** (https://github.com/its-hecker). Google supplies the native
Face/Citadel components; AOSP and LineageOS supply the camera/framework and ABI
compatibility sources. Immutable binary provenance is in `prebuilts.lock.json`;
source/license attribution is in `NOTICE` and the original file headers.
