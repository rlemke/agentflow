  scripts/drop-collections --yes     # clean DB
  scripts/easy.sh                    # rebuild + seed (flows + workflows + 401 handlers)
  # If using local runner:
  #scripts/start-runner --example osm-geocoder -- --log-format text
  # If using Docker agents:
 # docker compose --profile agents up -d --scale runner=5
