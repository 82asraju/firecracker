# Copyright 2018 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Tests that ensure the boot time to init process is within spec."""

import re
import time
import platform

# The maximum acceptable boot time in us.
MAX_BOOT_TIME_US = 150000
# NOTE: for aarch64 most of the boot time is spent by the kernel to unpack the
# initramfs in RAM. This time is influenced by the size and the compression
# method of the used initrd image.
INITRD_BOOT_TIME_US = 160000 if platform.machine() == "x86_64" else 500000
# TODO: Keep a `current` boot time in S3 and validate we don't regress
# Regex for obtaining boot time from some string.
TIMESTAMP_LOG_REGEX = r'Guest-boot-time\s+\=\s+(\d+)\s+us'


def test_no_boottime(test_microvm_with_api):
    """Check that boot timer device not present by default."""
    _ = _configure_and_run_vm(test_microvm_with_api)
    time.sleep(0.4)
    timestamps = re.findall(TIMESTAMP_LOG_REGEX,
                            test_microvm_with_api.log_data)
    assert not timestamps


def test_boottime_no_network(test_microvm_with_boottime_timer):
    """Check boot time of microVM without network."""
    test_microvm_with_boottime_timer.jailer.extra_args.update(
        {'boot-timer': None}
    )
    _ = _configure_and_run_vm(test_microvm_with_boottime_timer)
    time.sleep(0.4)
    boottime_us = _test_microvm_boottime(
            test_microvm_with_boottime_timer.log_data)
    print("Boot time with no network is: " + str(boottime_us) + " us")


def test_boottime_with_network(
        test_microvm_with_boottime_timer,
        network_config
):
    """Check boot time of microVM with network."""
    test_microvm_with_boottime_timer.jailer.extra_args.update(
        {'boot-timer': None}
    )
    _tap = _configure_and_run_vm(test_microvm_with_boottime_timer, {
        "config": network_config, "iface_id": "1"
    })
    time.sleep(0.4)
    boottime_us = _test_microvm_boottime(
            test_microvm_with_boottime_timer.log_data)
    print("Boot time with network configured is: " + str(boottime_us) + " us")


def test_initrd_boottime(
        test_microvm_with_initrd_timer):
    """Check boot time of microVM when using an initrd."""
    test_microvm_with_initrd_timer.jailer.extra_args.update(
        {'boot-timer': None}
    )
    _tap = _configure_and_run_vm(test_microvm_with_initrd_timer, initrd=True)
    time.sleep(0.8)
    boottime_us = _test_microvm_boottime(
        test_microvm_with_initrd_timer.log_data,
        max_time_us=INITRD_BOOT_TIME_US)
    print("Boot time with initrd is: " + str(boottime_us) + " us")


def _test_microvm_boottime(log_fifo_data, max_time_us=MAX_BOOT_TIME_US):
    """Auxiliary function for asserting the expected boot time."""
    boot_time_us = 0
    timestamps = re.findall(TIMESTAMP_LOG_REGEX, log_fifo_data)
    if timestamps:
        boot_time_us = int(timestamps[0])

    assert boot_time_us > 0
    assert boot_time_us < max_time_us
    return boot_time_us


def _configure_and_run_vm(microvm, network_info=None, initrd=False):
    """Auxiliary function for preparing microvm before measuring boottime."""
    microvm.spawn()

    # Machine configuration specified in the SLA.
    config = {
        'vcpu_count': 1,
        'mem_size_mib': 128
    }

    if initrd:
        config['add_root_device'] = False
        config['use_initrd'] = True

    microvm.basic_config(**config)

    if network_info:
        _tap, _, _ = microvm.ssh_network_config(
            network_info["config"],
            network_info["iface_id"]
        )

    microvm.start()
    return _tap if network_info else None
