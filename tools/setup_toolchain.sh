#!/bin/bash
# ============================================================
# 工具链一键初始化脚本（聆阅源构建 / dex 反编译）
# 用法: bash setup_toolchain.sh
# 存放: yingshi-backup 仓库 tools/setup_toolchain.sh
# 2026-10-01 实测可用
# ============================================================
set -e

TOOLCHAIN_DIR="${TOOLCHAIN_DIR:-$HOME/.local/share/hermes/toolchains}"
mkdir -p "$TOOLCHAIN_DIR"
cd "$TOOLCHAIN_DIR"

echo "== 工具链目录: $TOOLCHAIN_DIR =="

# ---------- JDK 17（华为云镜像，187MB 完整） ----------
if [ ! -x "$TOOLCHAIN_DIR/jdk-17.0.2/bin/java" ]; then
  echo ">> 下载 JDK 17（华为云镜像）..."
  curl -sL "https://mirrors.huaweicloud.com/openjdk/17.0.2/openjdk-17.0.2_linux-x64_bin.tar.gz" -o jdk17.tar.gz
  tar xzf jdk17.tar.gz
  rm -f jdk17.tar.gz
  echo ">> JDK 17 就绪: $TOOLCHAIN_DIR/jdk-17.0.2"
else
  echo ">> JDK 17 已存在"
fi
export JAVA_HOME="$TOOLCHAIN_DIR/jdk-17.0.2"

# ---------- Gradle 8.0（华为云镜像，124MB 完整） ----------
if [ ! -x "$TOOLCHAIN_DIR/gradle-8.0/bin/gradle" ]; then
  echo ">> 下载 Gradle 8.0（华为云镜像）..."
  curl -sL "https://mirrors.huaweicloud.com/gradle/gradle-8.0-bin.zip" -o gradle8.zip
  unzip -q gradle8.zip
  rm -f gradle8.zip
  echo ">> Gradle 8.0 就绪: $TOOLCHAIN_DIR/gradle-8.0"
else
  echo ">> Gradle 8.0 已存在"
fi

# ---------- r8.jar（D8 转 dex，dl.google.com 8.3MB） ----------
if [ ! -f "$TOOLCHAIN_DIR/r8.jar" ]; then
  echo ">> 下载 r8.jar（D8 3.3.75，dl.google.com）..."
  curl -sL "https://dl.google.com/dl/android/maven2/com/android/tools/r8/3.3.75/r8-3.3.75.jar" -o r8.jar
  echo ">> r8.jar 就绪: $TOOLCHAIN_DIR/r8.jar"
else
  echo ">> r8.jar 已存在"
fi

# ---------- 版本验证 ----------
echo ""
echo "== 版本验证 =="
"$JAVA_HOME/bin/java" -version 2>&1 | head -1
"$TOOLCHAIN_DIR/gradle-8.0/bin/gradle" --version 2>&1 | grep Gradle | head -1
"$JAVA_HOME/bin/java" -cp "$TOOLCHAIN_DIR/r8.jar" com.android.tools.r8.D8 --version 2>&1 | head -1

echo ""
echo "== 工具链全部就绪 =="
echo "  JAVA_HOME = $JAVA_HOME"
echo "  GRADLE    = $TOOLCHAIN_DIR/gradle-8.0/bin/gradle"
echo "  R8/D8     = $TOOLCHAIN_DIR/r8.jar"
