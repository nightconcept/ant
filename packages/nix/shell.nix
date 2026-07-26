{ pkgs, toolchain }:

let
  lib = pkgs.lib;
  zigPkg = if pkgs ? zig_0_16 then pkgs.zig_0_16 else pkgs.zig;
  nativeTuneFlag =
    if pkgs.stdenv.hostPlatform.isx86
    then "-march=native"
    else "-mcpu=native";
  optFlags = [
    nativeTuneFlag
    "-Qunused-arguments"
    "-fvisibility=hidden"
    "-fvisibility-inlines-hidden"
    "-fno-math-errno"
    "-fno-trapping-math"
    "-fno-stack-protector"
    "-mllvm"
    "-enable-machine-outliner=never"
  ];
  optArgs = lib.concatStringsSep " " optFlags;
in
pkgs.mkShellNoCC {
  packages = [
    toolchain.bintools
    toolchain.clang
    toolchain.compilerRt
    pkgs.meson
    pkgs.ninja
    pkgs.cmake
    pkgs.pkg-config
    pkgs.python3
    pkgs.nodejs_22
    pkgs.git
    pkgs.curl
    zigPkg
    pkgs.just
  ];

  CFLAGS = optArgs;
  CXXFLAGS = optArgs;
  NIX_CFLAGS_COMPILE = optArgs;
  NIX_ENFORCE_NO_NATIVE = "0";
  LDFLAGS = lib.optionalString pkgs.stdenv.hostPlatform.isDarwin
    "-resource-dir=${toolchain.compilerRt}";

  CC = "${toolchain.clang}/bin/clang";
  CXX = "${toolchain.clang}/bin/clang++";

  LD = lib.optionalString pkgs.stdenv.hostPlatform.isDarwin "${toolchain.bintools}/bin/ld";
  AR = lib.optionalString pkgs.stdenv.hostPlatform.isDarwin "${toolchain.bintools}/bin/ar";
  RANLIB = lib.optionalString pkgs.stdenv.hostPlatform.isDarwin "${toolchain.bintools}/bin/ranlib";
  STRIP = lib.optionalString pkgs.stdenv.hostPlatform.isDarwin "${toolchain.bintools}/bin/strip";

  shellHook =
    if pkgs.stdenv.hostPlatform.isDarwin then ''
      export SDKROOT="$(/usr/bin/xcrun --show-sdk-path)"
    '' else ''
      unset SDKROOT
    '';
}
