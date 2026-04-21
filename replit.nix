{ pkgs }: {
  deps = [
    pkgs.python310
    pkgs.python310Packages.pip
    pkgs.python310Packages.virtualenv
    pkgs.nodejs_20
    pkgs.ffmpeg
    pkgs.libsndfile
    pkgs.portaudio
    pkgs.pkg-config
    pkgs.openssl
    pkgs.zlib
    pkgs.libffi
  ];

  env = {
    PYTHONPATH = "${pkgs.python310}/lib/python3.10/site-packages";
    LD_LIBRARY_PATH = "${pkgs.libsndfile}/lib:${pkgs.portaudio}/lib:${pkgs.openssl.out}/lib:${pkgs.zlib}/lib:${pkgs.libffi}/lib";
    C_INCLUDE_PATH = "${pkgs.libsndfile}/include:${pkgs.portaudio}/include";
  };
}