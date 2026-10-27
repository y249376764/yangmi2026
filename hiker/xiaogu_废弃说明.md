小咕（咕噜咕噜私有协议）项目已放弃，不再维护。

原因：站点只走 P-256 ECDH + AES-256-GCM 私有加密协议，无明文接口。规则依赖 javax.crypto / java.net / java.security / java.util.zip 四个 Java 包，真机 JSEngine 对这几个包的放行情况无法保证，导入后持续报错。

现在保留的三条规则：蜘蛛🕷️、聚影、网盘资源。
