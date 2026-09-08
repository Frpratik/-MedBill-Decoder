CREATE INDEX rates_code ON payment_rates(code,modifier,category);

CREATE TABLE build_metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);

CREATE TABLE code_descriptions(code TEXT NOT NULL, modifier TEXT NOT NULL,
      description TEXT NOT NULL, source_id TEXT NOT NULL REFERENCES sources(id),
      source_row INTEGER NOT NULL, PRIMARY KEY(code,modifier)) WITHOUT ROWID;

CREATE TABLE hcpcs_descriptions(code TEXT PRIMARY KEY, long_description TEXT NOT NULL,
      short_description TEXT NOT NULL, added_date TEXT NOT NULL, action_date TEXT NOT NULL,
      termination_date TEXT NOT NULL, action TEXT NOT NULL, coverage TEXT NOT NULL,
      source_id TEXT NOT NULL REFERENCES sources(id), source_row INTEGER NOT NULL);

CREATE TABLE hcpcs_modifiers(
  code TEXT,
  long_description TEXT,
  short_description TEXT,
  added_date TEXT,
  action_date TEXT,
  termination_date TEXT,
  "action" TEXT,
  coverage TEXT,
  source_id TEXT,
  source_row INT
);

CREATE TABLE ingestion_issues(kind TEXT NOT NULL, source_id TEXT NOT NULL, count INTEGER NOT NULL,
      detail TEXT NOT NULL);

CREATE TABLE payment_rates(year TEXT NOT NULL,carrier TEXT NOT NULL,locality TEXT NOT NULL,code TEXT NOT NULL,modifier TEXT NOT NULL,nonfacility_cents INTEGER NOT NULL CHECK(nonfacility_cents>=0),facility_cents INTEGER NOT NULL CHECK(facility_cents>=0),filler TEXT NOT NULL,pctc TEXT NOT NULL,status TEXT NOT NULL,multiple_surgery TEXT NOT NULL,therapy_nonfacility_cents INTEGER NOT NULL CHECK(therapy_nonfacility_cents>=0),therapy_facility_cents INTEGER NOT NULL CHECK(therapy_facility_cents>=0),opps_indicator TEXT NOT NULL,opps_nonfacility_cents INTEGER NOT NULL CHECK(opps_nonfacility_cents>=0),opps_facility_cents INTEGER NOT NULL CHECK(opps_facility_cents>=0),category TEXT NOT NULL,source_id TEXT NOT NULL,source_row INTEGER NOT NULL CHECK(source_row>=0),
        FOREIGN KEY(source_id) REFERENCES sources(id), PRIMARY KEY(category,carrier,locality,code,modifier)) WITHOUT ROWID;

CREATE TABLE payment_revisions(
  year TEXT,
  carrier TEXT,
  locality TEXT,
  code TEXT,
  modifier TEXT,
  nonfacility_cents INT,
  facility_cents INT,
  filler TEXT,
  pctc TEXT,
  status TEXT,
  multiple_surgery TEXT,
  therapy_nonfacility_cents INT,
  therapy_facility_cents INT,
  opps_indicator TEXT,
  opps_nonfacility_cents INT,
  opps_facility_cents INT,
  category TEXT,
  source_id TEXT,
  source_row INT
);

CREATE TABLE rvu_policy(code TEXT NOT NULL, modifier TEXT NOT NULL, category TEXT NOT NULL,
      status TEXT NOT NULL, nonfacility_na TEXT NOT NULL, facility_na TEXT NOT NULL,
      source_id TEXT NOT NULL REFERENCES sources(id), source_row INTEGER NOT NULL,
      PRIMARY KEY(code,modifier,category)) WITHOUT ROWID;

CREATE TABLE sources(id TEXT PRIMARY KEY, url TEXT NOT NULL, archive TEXT NOT NULL,
      sha256 TEXT NOT NULL, member TEXT NOT NULL, release TEXT NOT NULL,
      retrieved_date TEXT NOT NULL, copyright_notice TEXT NOT NULL);