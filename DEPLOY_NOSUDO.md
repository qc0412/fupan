# Fupan 无 sudo 部署改造说明

目标：以后由当前 `ubuntu` 用户直接完成 `fupan` 的前后端部署，不再要求聊天代理拿到 `sudo`。

## 现状

- 后端服务 `/etc/systemd/system/fupan.service` 的运行用户已经是 `ubuntu`。
- gunicorn control socket：`/home/ubuntu/.gunicorn/gunicorn.ctl`
- 前端线上目录当前是 root 管理（`/var/www/fupan` 需要一次性授权）

## 新增脚本

- `reload_backend.sh`
  - 无 sudo 后端热重载
  - 优先通过 gunicorn control socket 发送 `hup`
- `deploy_nosudo.sh`
  - 无 sudo 前端构建并 `rsync` 到站点目录
  - 需要目标目录对 `ubuntu` 可写

## 一次性 root 初始化（只做一次）

### 方案 A：继续用 `/var/www/fupan`（推荐最小改动）

```bash
sudo mkdir -p /var/www/fupan
sudo chown -R ubuntu:ubuntu /var/www/fupan
```

然后以后发布前端只需要：

```bash
cd /home/ubuntu/fupan && ./deploy_nosudo.sh
```

### 方案 B：保持 root 所有权，但给 ACL

```bash
sudo mkdir -p /var/www/fupan
sudo setfacl -R -m u:ubuntu:rwx /var/www/fupan
sudo setfacl -dR -m u:ubuntu:rwx /var/www/fupan
```

## 后端以后如何发

```bash
cd /home/ubuntu/fupan && ./reload_backend.sh
```

## 建议的未来部署顺序

```bash
cd /home/ubuntu/fupan
./reload_backend.sh
./deploy_nosudo.sh
```

## 说明

- 当前聊天代理卡住的不是 `reclaude`，而是 provider 侧 `elevated` 策略。
- 把部署链路改成无 sudo 后，代理可直接完成部署，不再需要系统提权。
