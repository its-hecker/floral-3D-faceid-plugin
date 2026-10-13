# SPDX-License-Identifier: Apache-2.0
# Product bootstrap can run before Android defines the my-dir helper.
FLORAL_FACEID_PLUGIN_PATH := $(patsubst %/,%,$(dir $(lastword $(MAKEFILE_LIST))))
ifeq ($(wildcard $(FLORAL_FACEID_PLUGIN_PATH)/generated/profile.json),)
$(error Fetch prebuilts, apply the guarded framework fixes and run $(FLORAL_FACEID_PLUGIN_PATH)/tools/prepare.py before building)
endif
FLORAL_FACEID_READY := $(shell python3 "$(FLORAL_FACEID_PLUGIN_PATH)/tools/verify_ready.py" 2>&1)
ifneq ($(FLORAL_FACEID_READY),ready)
$(error $(FLORAL_FACEID_READY))
endif
include $(FLORAL_FACEID_PLUGIN_PATH)/generated/profile.mk

PRODUCT_SOONG_NAMESPACES += $(FLORAL_FACEID_PLUGIN_PATH)
# Inherit this file after the base device and vendor products.
FLORAL_FACEID_REPLACED_PACKAGES := \
    android.hardware.biometrics.face@1.0-service.google \
    android.hardware.keymaster@4.1-service.citadel \
    android.hardware.keymaster@4.1-impl.nos \
    vendor.google.airbrush@1.0-service \
    android.hardware.neuralnetworks@1.2-service-noronha \
    libface-calibration-proto libface-enroll-proto libfaceauth-util libairbrush-pixel \
    libautocalsolvers libcamera2ndk_v33_face libbase-v33 libcrypto-v33 libstagefright_foundation-v33 \
    manifest_face.xml
PRODUCT_PACKAGES := $(filter-out $(FLORAL_FACEID_REPLACED_PACKAGES),$(PRODUCT_PACKAGES))
FLORAL_FACEID_REPLACED_COPY_DESTS := \
    $(TARGET_COPY_OUT_VENDOR)/etc/init/android.hardware.biometrics.face@1.0-service.google.rc \
    $(TARGET_COPY_OUT_VENDOR)/etc/init/android.hardware.keymaster@4.1-service.citadel.rc \
    $(TARGET_COPY_OUT_VENDOR)/etc/permissions/android.hardware.biometrics.face.xml
PRODUCT_COPY_FILES := $(filter-out $(addprefix %:,$(FLORAL_FACEID_REPLACED_COPY_DESTS)),$(PRODUCT_COPY_FILES))

PRODUCT_PACKAGES += \
    FloralFaceIDHal FloralFaceIDCitadelKeymaster FloralFaceIDCitadelImpl \
    FloralFaceIDCalibrationProto FloralFaceIDEnrollmentProto FloralFaceIDAuthUtil \
    FloralFaceIDAirbrushClient FloralFaceIDAirbrushService FloralFaceIDNeuralNetworks \
    FloralFaceIDAutocalSolvers FloralFaceIDCameraNDK \
    FloralFaceIDV33Base FloralFaceIDV33Crypto FloralFaceIDV33Foundation \
    FloralFaceIDFrameworkOverlay \
    android.hardware.thermal@2.0.vendor:64 \
    android.hardware.biometrics.face@1.0.vendor:64
ifeq ($(FLORAL_FACEID_ADD_VINTF),true)
PRODUCT_PACKAGES += FloralFaceIDManifest
endif
PRODUCT_COPY_FILES += \
    $(FLORAL_FACEID_PLUGIN_PATH)/configs/android.hardware.biometrics.face.xml:$(TARGET_COPY_OUT_VENDOR)/etc/permissions/android.hardware.biometrics.face.xml
