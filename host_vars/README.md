# host_vars — Windows WinRM 密码（不入 git）

Ansible 会自动加载 `/etc/ansible/host_vars/<主机IP>.yml`，把 `ansible_password`
注入给 inventory.ini 里对应的主机。这样 **inventory.ini 可以安全提交（不含密码）**，
密码只在本目录（已 gitignore，挂载进容器）。

## 文件

| 文件 | 内容 |
|------|------|
| `10.0.0.10.yml`  | `ansible_password: <10 的 administrator 密码>` |
| `10.0.0.253.yml` | `ansible_password: <253 的 administrator 密码>` |
| `10.0.0.254.yml` | `ansible_password: <254 的 administrator 密码>` |

`*.yml` 已在 `.gitignore` 中，不会被提交。

## 在监控机 10.0.0.15 上部署

本目录通过 docker-compose 挂载到容器 `/etc/ansible/host_vars`。只需把这三个 yml
放到 15 的 `/opt/ops-relay/host_vars/` 下即可（CI 的 `git reset --hard` 不会动
gitignore 的文件）。

```bash
# 在 15 上
ls /opt/ops-relay/host_vars/   # 应能看到 10.0.0.10.yml 等
```

## 改密码

直接改对应 yml 文件，无需重启容器（Ansible 每次采集都重新读取）。
