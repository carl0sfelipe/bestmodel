# Backup diário (systemd --user)

`../backup.sh` tira a cópia off-host; estas unidades a agendam.

Instalar numa máquina nova:

    cp deploy/systemd/bestmodel-backup.* ~/.config/systemd/user/
    systemctl --user daemon-reload
    systemctl --user enable --now bestmodel-backup.timer
    loginctl enable-linger "$USER"     # senão o timer só roda com sessão aberta

O `enable-linger` não é opcional: sem ele o backup para no dia em que a
sessão gráfica cair, silenciosamente.

Conferir: `systemctl --user list-timers bestmodel-backup.timer`
Rodar na hora: `systemctl --user start bestmodel-backup.service`
