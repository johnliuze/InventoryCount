CREATE TABLE items (
    item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_code TEXT NOT NULL UNIQUE
);

CREATE TABLE bins (
    bin_id INTEGER PRIMARY KEY AUTOINCREMENT,
    bin_code TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS inventory (
    inventory_id INTEGER PRIMARY KEY AUTOINCREMENT,
    bin_id INTEGER,
    item_id INTEGER,
    box_count INTEGER,
    pieces_per_box INTEGER,
    total_pieces INTEGER,
    FOREIGN KEY (bin_id) REFERENCES bins(bin_id),
    FOREIGN KEY (item_id) REFERENCES items(item_id)
);

CREATE TABLE IF NOT EXISTS input_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    bin_code TEXT,
    item_code TEXT,
    box_count INTEGER,
    pieces_per_box INTEGER,
    total_pieces INTEGER,
    timestamp TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime'))
); 