# Collegare rAIl a Hermes da un'altra macchina — guida facile

rAIl deve raggiungere **Hermes `api_server`** (porta **8642**). Servono 2 cose:
una **strada** (VPN o tunnel SSH) e la **chiave** di autenticazione.

## Passo 1 — cos'è la macchina con Hermes?

Sulla macchina **Hermes** apri `~/.hermes/config.yaml` e cerca `api_server:`:

```yaml
gateway:
  platforms: '["discord"]'
  api_server:
    enabled: true
    extra:
      host: 0.0.0.0        # <-- se manca, Hermes è SOLO locale
      port: 8642
      key: <QUI_C'È_LA_CHIAVE>   # <-- copiala, serve al Passo 3
```

- `host` non c'è o è `127.0.0.1` → Hermes è irraggiungibile da fuori:
  metti `host: 0.0.0.0` e **riavvia Hermes**.
- Se la rete fra le due macchine è **bloccata/firewall** → installa
  **Tailscale su entrambe** (`tailscale up`) e usa l'IP Tailscale di Hermes:
  l'IP `169.58.151.218` non è un IP Tailscale, quindi così com'è non funziona;
  la via alternativa è il **tunnel SSH** (Passo 2).

## Passo 2 — la strada (tunnel SSH)

```bash
# 1. sulla macchina rAIl (es. webtop): crea la chiave
ssh-keygen -t ed25519 -f ~/.ssh/hermes_rail -N "" -C "rail-webtop"

# 2. incolla UNA riga in ~/.ssh/authorized_keys della macchina Hermes
#    (cat ~/.ssh/hermes_rail.pub dalla webtop)

# 3. sempre sulla macchina rAIl, apri il tunnel (2° terminale, tenerlo aperto):
ssh -i ~/.ssh/hermes_rail -N -L 8642:localhost:8642 hermes@<IP-di-Hermes>
```

Ora `localhost:8642` **dentro rAIl** punta a Hermes. Verifica:

```bash
curl -m3 -o /dev/null -w "%{http_code}\n" --noproxy '*' http://localhost:8642/v1/models
# 200 = ok. 000/404 = la strada non è aperta (controlla Passo 1 e il tunnel)
```

## Passo 3 — configura rAIl

```bash
cd ~/rAIl && python3 setup.py
# → scegli l'opzione API (tunnel SSH) → endpoint http://localhost:8642/v1/chat/completions
# → INCOLLA la chiave `key:` vista al Passo 1
```

## Passo 4 — prova

```bash
python3 -m hermes_avatar.main
```

Prima di `👤 Tu:` devi vedere **`🔌 Hermes API: http://...`**.
Se vedi `⚠️ Nessun canale Hermes attivo` → o la chiave è sbagliata (401)
o il tunnel è chiuso (`000` in Passo 2): riapri il tunnel e riprova.

## Problemi comuni

| Sintomo | Causa | Fix |
|---|---|---|
| `404` anche da Hermes con la chiave giusta | proxy/squid che intercetta | `export NO_PROXY=localhost,127.0.0.1` (già in `rail-tunnel.sh`) |
| `Connection refused` con `localhost:8642` | tunnel spento | riapri il tunnel (Passo 2) |
| `API disattivata` | `RAIL_API_ENABLED` ≠ true o chiave vuota | re-importa setup (`python3 -m setup --api ... --api-key ... --api-enabled true`) |
| 401/403 con URL `8644`/`hermesxrail.xyz-xyz.party` | stai usando la **dashboard**, non l'API | usa l'URL `...:8642/v1/chat/completions` + chiave `api_server` |

> ⚠️ La chiave = il tuo account Hermes. Non committarla, non condividerla.
> I domini `*.xyz-xyz.party` espongono dashboard (4180) e 8644, **non** l'API chat.
