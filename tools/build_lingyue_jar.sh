#!/bin/bash
# ============================================================
# 聆阅源 jar 一键构建脚本（我的听书源）
# 用法: bash build_lingyue_jar.sh [wenge.jar 路径]
# 依赖: setup_toolchain.sh 已装好的 JDK17 + Gradle8 + r8.jar
# 存放: yingshi-backup 仓库 tools/build_lingyue_jar.sh
# 2026-10-01 v4 实测
# ============================================================
set -e

TOOLCHAIN_DIR="${TOOLCHAIN_DIR:-$HOME/.local/share/hermes/toolchains}"
export JAVA_HOME="$TOOLCHAIN_DIR/jdk-17.0.2"
export PATH="$JAVA_HOME/bin:$TOOLCHAIN_DIR/gradle-8.0/bin:$PATH"
WENGE_JAR="${1:-/tmp/wenge.jar}"   # 含听友FM解密逻辑的旧 jar（可选）
WORK=/tmp/lingyue_build
mkdir -p "$WORK"

echo "== 1. 拉取 tingshu 源码（若缺失） =="
if [ ! -d /tmp/tingshu_src ]; then
  git clone --depth 1 --filter=blob:none --sparse "https://github.com/eprendre/tingshu.git" /tmp/tingshu_src
  cd /tmp/tingshu_src
  git sparse-checkout set CustomSources
else
  cd /tmp/tingshu_src
fi

echo "== 2. 编译 Kotlin 源（跳过 dexTask） =="
cd /tmp/tingshu_src/CustomSources
gradle jar --no-daemon -x dexTask 2>&1 | grep -E "BUILD|error" | tail -2

echo "== 3. 下载 Fuel/json 依赖（阿里云镜像） =="
cd "$WORK"
[ -f fuel.jar ] || curl -sL "https://maven.aliyun.com/repository/public/com/github/kittinunf/fuel/fuel/2.3.1/fuel-2.3.1.jar" -o fuel.jar
[ -f fuel-json.jar ] || curl -sL "https://maven.aliyun.com/repository/public/com/github/kittinunf/fuel/fuel-json/2.3.1/fuel-json-2.3.1.jar" -o fuel-json.jar
[ -f orgjson.jar ] || curl -sL "https://maven.aliyun.com/repository/public/org/json/json/20140107/json-20140107.jar" -o orgjson.jar

echo "== 4. D8 转 dex（含依赖） =="
rm -rf "$WORK/dex" && mkdir -p "$WORK/dex"
"$JAVA_HOME/bin/java" -cp "$TOOLCHAIN_DIR/r8.jar" com.android.tools.r8.D8 \
  --output "$WORK/dex" \
  /tmp/tingshu_src/CustomSources/build/libs/CustomSources-1.0-SNAPSHOT.jar \
  "$WORK/fuel.jar" "$WORK/fuel-json.jar" "$WORK/orgjson.jar" \
  --lib "$JAVA_HOME" 2>&1 | grep -viE "^Info:|^Warning:" | tail -2

echo "== 5. 合并 wenge dex（含听友FM 等好站） =="
if [ -f "$WENGE_JAR" ]; then
  python3 -c "
import zipfile
z=zipfile.ZipFile('$WENGE_JAR')
open('$WORK/wenge_classes.dex','wb').write(z.read('classes.dex'))
print('wenge dex 解出')
"
  rm -rf "$WORK/merge" && mkdir -p "$WORK/merge"
  "$JAVA_HOME/bin/java" -cp "$TOOLCHAIN_DIR/r8.jar" com.android.tools.r8.D8 \
    --output "$WORK/merge" \
    "$WORK/wenge_classes.dex" "$WORK/dex/classes.dex" \
    --lib "$JAVA_HOME" 2>&1 | grep -viE "^Info:|^Warning:" | tail -2
  FINAL_DEX="$WORK/merge/classes.dex"
else
  FINAL_DEX="$WORK/dex/classes.dex"
fi

echo "== 6. 打包 jar =="
python3 -c "
import zipfile
z=zipfile.ZipFile('$WORK/sources_by_lingyue.jar','w',zipfile.ZIP_DEFLATED)
z.write('$FINAL_DEX','classes.dex')
z.close()
print('打包完成')
"
ls -la "$WORK/sources_by_lingyue.jar"
echo ""
echo "== 构建产物: $WORK/sources_by_lingyue.jar =="
echo "（上传到 GitHub 仓库 sources_by_lingyue.jar 覆盖即可，链接不变）"
