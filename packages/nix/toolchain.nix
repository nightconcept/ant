{ pkgs }: {
  clang =
    if pkgs.stdenv.hostPlatform.isDarwin
    then pkgs.llvmPackages_21.clang-unwrapped.out
    else pkgs.llvmPackages_21.clang;
  compilerRt = pkgs.llvmPackages_21.compiler-rt;
  bintools =
    if pkgs.stdenv.hostPlatform.isDarwin
    then pkgs.darwin.binutils-unwrapped
    else pkgs.llvmPackages_21.bintools;
  inherit (pkgs.llvmPackages_21) stdenv;
}
