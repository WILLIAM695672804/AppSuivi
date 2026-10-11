-- Projet SASI — schéma de la base de données
-- PostgreSQL, avec TimescaleDB si elle est disponible
-- (cahier des charges technique, chapitre 4)
--
-- Création :  psql -U sasi -d sasi -f base/schema.sql
--
-- TimescaleDB apporte le découpage des tables de mesures, leur compression et
-- leur purge automatique. Elle n'est pas indispensable au fonctionnement : sans
-- elle, les mêmes tables existent en PostgreSQL ordinaire, et tout marche — un
-- peu moins vite sur de longues périodes, sans purge automatique. Le schéma
-- s'adapte donc à ce qui est installé, pour qu'un poste de développement
-- n'ait pas à télécharger une image de 550 Mo.

DO $$ BEGIN
    CREATE EXTENSION IF NOT EXISTS timescaledb;
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'TimescaleDB indisponible : le schéma se limite à PostgreSQL.';
END $$;

-- ---------------------------------------------------------------- référentiel
CREATE TABLE IF NOT EXISTS site (
    id            TEXT PRIMARY KEY,
    nom           TEXT NOT NULL,
    secteur       TEXT,
    fuseau        TEXT NOT NULL DEFAULT 'Africa/Douala'
);

CREATE TABLE IF NOT EXISTS zone (
    site          TEXT REFERENCES site(id),
    numero        INTEGER NOT NULL,
    nom           TEXT NOT NULL,
    PRIMARY KEY (site, numero)
);

CREATE TABLE IF NOT EXISTS famille (
    code          TEXT PRIMARY KEY,
    nom           TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS camera (
    id            TEXT PRIMARY KEY,
    site          TEXT REFERENCES site(id),
    zone          INTEGER,
    modele        TEXT,
    adresse       TEXT,
    adaptateur    TEXT NOT NULL DEFAULT 'jumeau',
    resolution    TEXT,
    precision_c   REAL,
    distance_m    REAL,
    emissivite    REAL
);

CREATE TABLE IF NOT EXISTS equipement (
    id                  TEXT PRIMARY KEY,
    site                TEXT REFERENCES site(id),
    nom                 TEXT NOT NULL,
    zone                INTEGER NOT NULL,
    famille             TEXT REFERENCES famille(code),
    camera              TEXT REFERENCES camera(id),
    criticite           SMALLINT NOT NULL CHECK (criticite BETWEEN 1 AND 3),
    plage_basse         REAL NOT NULL,
    plage_haute         REAL NOT NULL,
    temps_montee_min    REAL NOT NULL,
    seuil_inspection    REAL,
    seuil_urgence       REAL,
    action_conseillee   TEXT,
    position_x          REAL,
    position_y          REAL,
    en_maintenance      BOOLEAN NOT NULL DEFAULT FALSE
);

-- contour dessiné sur l'image d'une caméra
CREATE TABLE IF NOT EXISTS zone_image (
    equipement    TEXT REFERENCES equipement(id),
    camera        TEXT REFERENCES camera(id),
    contour       JSONB NOT NULL,          -- [[x1,y1],[x2,y2],…]
    PRIMARY KEY (equipement, camera)
);

CREATE TABLE IF NOT EXISTS groupe_jumeaux (
    nom           TEXT NOT NULL,
    equipement    TEXT REFERENCES equipement(id),
    PRIMARY KEY (nom, equipement)
);

-- ---------------------------------------------------------------- mesures
CREATE TABLE IF NOT EXISTS mesure (
    horodatage    TIMESTAMPTZ NOT NULL,
    equipement    TEXT NOT NULL,
    t_max         REAL NOT NULL,
    t_moy         REAL,
    t_min         REAL,
    source        TEXT NOT NULL DEFAULT 'camera'   -- 'camera' ou 'jumeau'
);
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
        PERFORM create_hypertable('mesure', 'horodatage', if_not_exists => TRUE);
    END IF;
END $$;
CREATE INDEX IF NOT EXISTS mesure_equipement_temps ON mesure (equipement, horodatage DESC);

CREATE TABLE IF NOT EXISTS contexte (
    horodatage    TIMESTAMPTZ NOT NULL,
    equipement    TEXT NOT NULL,
    etat          TEXT NOT NULL,           -- 'marche' ou 'arret'
    charge_pct    REAL
);
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
        PERFORM create_hypertable('contexte', 'horodatage', if_not_exists => TRUE);
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS ambiance (
    horodatage    TIMESTAMPTZ NOT NULL,
    site          TEXT NOT NULL,
    zone          INTEGER NOT NULL,
    t_ambiante    REAL,
    humidite_pct  REAL
);
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
        PERFORM create_hypertable('ambiance', 'horodatage', if_not_exists => TRUE);
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS prediction (
    horodatage    TIMESTAMPTZ NOT NULL,
    equipement    TEXT NOT NULL,
    t_attendue    REAL NOT NULL,
    ecart         REAL,
    pente         REAL,
    score         REAL,
    niveau        TEXT
);
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
        PERFORM create_hypertable('prediction', 'horodatage', if_not_exists => TRUE);
    END IF;
END $$;

-- ---------------------------------------------------------------- alertes
CREATE TABLE IF NOT EXISTS alerte (
    id                TEXT PRIMARY KEY,
    equipement        TEXT REFERENCES equipement(id),
    niveau            TEXT NOT NULL,
    etat              TEXT NOT NULL,       -- ouverte / acquittee / assignee / cloturee
    debut             TIMESTAMPTZ NOT NULL,
    fin               TIMESTAMPTZ,
    t_mesuree         REAL,
    t_attendue        REAL,
    raison            TEXT,
    facteurs          JSONB,
    action_conseillee TEXT,
    assignee_a        TEXT
);
CREATE INDEX IF NOT EXISTS alerte_etat ON alerte (etat, debut DESC);

CREATE TABLE IF NOT EXISTS alerte_evenement (
    id            BIGSERIAL PRIMARY KEY,
    alerte        TEXT REFERENCES alerte(id),
    horodatage    TIMESTAMPTZ NOT NULL,
    type          TEXT NOT NULL,           -- creation, montee_de_niveau, acquittement…
    par           TEXT,
    details       JSONB
);

CREATE TABLE IF NOT EXISTS intervention (
    id            BIGSERIAL PRIMARY KEY,
    alerte        TEXT REFERENCES alerte(id),
    horodatage    TIMESTAMPTZ NOT NULL,
    par           TEXT NOT NULL,
    constat       TEXT NOT NULL,
    travaux       TEXT,
    photo         TEXT,
    justifiee     BOOLEAN NOT NULL
);

CREATE TABLE IF NOT EXISTS notification (
    id            BIGSERIAL PRIMARY KEY,
    alerte        TEXT REFERENCES alerte(id),
    horodatage    TIMESTAMPTZ NOT NULL,
    canal         TEXT NOT NULL,           -- notification / sms
    destinataire  TEXT NOT NULL,
    reussie       BOOLEAN NOT NULL DEFAULT TRUE,
    motif         TEXT
);

CREATE TABLE IF NOT EXISTS alerte_technique (
    id            BIGSERIAL PRIMARY KEY,
    horodatage    TIMESTAMPTZ NOT NULL,
    camera        TEXT,
    type          TEXT NOT NULL,           -- camera_muette / camera_figee / mesure_ecartee
    message       TEXT,
    resolue       BOOLEAN NOT NULL DEFAULT FALSE
);

-- ---------------------------------------------------------------- utilisateurs
CREATE TABLE IF NOT EXISTS utilisateur (
    identifiant   TEXT PRIMARY KEY,
    nom           TEXT NOT NULL,
    mot_de_passe  TEXT NOT NULL,           -- empreinte bcrypt
    telephone     TEXT,
    role          TEXT NOT NULL,           -- technicien / securite / direction / admin
    actif         BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS abonnement (
    id            BIGSERIAL PRIMARY KEY,
    utilisateur   TEXT REFERENCES utilisateur(identifiant),
    zone          INTEGER,
    niveau_min    TEXT NOT NULL DEFAULT 'surveillance',
    heure_debut   SMALLINT NOT NULL DEFAULT 0,
    heure_fin     SMALLINT NOT NULL DEFAULT 24,
    ordre         SMALLINT NOT NULL DEFAULT 1        -- ordre d'escalade
);

CREATE TABLE IF NOT EXISTS journal_audit (
    id            BIGSERIAL PRIMARY KEY,
    horodatage    TIMESTAMPTZ NOT NULL DEFAULT now(),
    utilisateur   TEXT,
    action        TEXT NOT NULL,
    details       JSONB
);

-- ---------------------------------------------------------------- IA
CREATE TABLE IF NOT EXISTS modele (
    id            BIGSERIAL PRIMARY KEY,
    famille       TEXT NOT NULL,
    version       TEXT NOT NULL,
    entraine_le   TIMESTAMPTZ NOT NULL,
    periode       TEXT,
    erreur_moy    REAL,
    en_service    BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS calibrage_zone (
    equipement       TEXT REFERENCES equipement(id),
    regime           TEXT NOT NULL,        -- etabli / transitoire
    biais            REAL NOT NULL,
    dispersion       REAL NOT NULL,
    fin_apprentissage TIMESTAMPTZ,
    PRIMARY KEY (equipement, regime)
);

CREATE TABLE IF NOT EXISTS evaluation (
    id               BIGSERIAL PRIMARY KEY,
    horodatage       TIMESTAMPTZ NOT NULL DEFAULT now(),
    lot              TEXT,
    taux_detection   REAL,
    part_fausses     REAL,
    delai_median_s   REAL,
    details          JSONB
);

-- ---------------------------------------------------------------- conservation
-- Compression après 7 jours, purge après 1 an, moyennes par minute : tout cela
-- relève de TimescaleDB. Sans elle, les tables restent complètes et c'est à
-- l'exploitant de les purger.
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
        RAISE NOTICE 'TimescaleDB absente : ni compression, ni purge automatique,'
                     ' ni moyennes par minute. Le reste fonctionne.';
        RETURN;
    END IF;

    -- Mesures détaillées : compressées après 7 jours, supprimées après 1 an.
    EXECUTE 'ALTER TABLE mesure SET (timescaledb.compress,'
            ' timescaledb.compress_segmentby = ''equipement'')';
    PERFORM add_compression_policy('mesure', INTERVAL '7 days', if_not_exists => TRUE);
    PERFORM add_retention_policy('mesure', INTERVAL '1 year', if_not_exists => TRUE);

    -- Moyennes par minute, conservées sans limite.
    EXECUTE 'CREATE MATERIALIZED VIEW IF NOT EXISTS mesure_minute'
            ' WITH (timescaledb.continuous) AS'
            ' SELECT time_bucket(''1 minute'', horodatage) AS minute,'
            '        equipement,'
            '        avg(t_max)  AS t_max_moy,'
            '        max(t_max)  AS t_max_max,'
            '        avg(t_moy)  AS t_moy'
            ' FROM mesure'
            ' GROUP BY minute, equipement';
END $$;
