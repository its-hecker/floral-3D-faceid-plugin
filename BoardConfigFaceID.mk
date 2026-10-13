# SPDX-License-Identifier: Apache-2.0
# Product bootstrap can run before Android defines the my-dir helper.
FLORAL_FACEID_PLUGIN_PATH := $(patsubst %/,%,$(dir $(lastword $(MAKEFILE_LIST))))
BOARD_VENDOR_SEPOLICY_DIRS += $(FLORAL_FACEID_PLUGIN_PATH)/sepolicy/vendor
