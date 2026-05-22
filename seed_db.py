import os
import json
import re
import sqlite3

def seed_database():
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "database.db")
    thuvien_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data_thuvienmau.txt")
    mauson_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mauson.txt")

    print(f"Database path: {db_path}")
    print(f"Library path: {thuvien_path}")
    print(f"Colors path: {mauson_path}")

    # Connect to SQLite
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Drop existing tables to ensure clean migration/seed
    cursor.execute("DROP TABLE IF EXISTS paint_colors")
    cursor.execute("DROP TABLE IF EXISTS brands")
    cursor.execute("DROP TABLE IF EXISTS layers")
    cursor.execute("DROP TABLE IF EXISTS collections")
    cursor.execute("DROP TABLE IF EXISTS project_types")

    # Create tables with specified structures and types
    cursor.execute("""
        CREATE TABLE project_types (
            id INTEGER PRIMARY KEY,
            name TEXT,
            slug TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE collections (
            id TEXT PRIMARY KEY,
            name TEXT,
            description TEXT,
            number_of_floors INTEGER,
            number_of_facades INTEGER,
            project_type_id INTEGER,
            FOREIGN KEY (project_type_id) REFERENCES project_types(id)
        )
    """)

    # Index for project_type_id in collections
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_collections_project_type_id ON collections(project_type_id)")

    # Complete layers table storing all fields including nested file properties
    cursor.execute("""
        CREATE TABLE layers (
            id TEXT PRIMARY KEY,
            collection_id TEXT,
            name TEXT,
            image_url TEXT,
            image_path TEXT,
            image_mime_type TEXT,
            layer_type TEXT,
            layer_type_display TEXT,
            z_index INTEGER,
            opacity REAL,
            visible INTEGER,
            FOREIGN KEY (collection_id) REFERENCES collections(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE brands (
            id INTEGER PRIMARY KEY,
            name TEXT
        )
    """)

    # Paint colors table with complete specifications including description
    cursor.execute("""
        CREATE TABLE paint_colors (
            id INTEGER PRIMARY KEY,
            brand_id INTEGER,
            name TEXT,
            paint_code TEXT,
            hex_code TEXT,
            category TEXT,
            finish TEXT,
            coverage TEXT,
            description TEXT,
            FOREIGN KEY (brand_id) REFERENCES brands(id)
        )
    """)

    # Indices for performance tuning in paint_colors
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_paint_colors_paint_code ON paint_colors(paint_code)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_paint_colors_hex_code ON paint_colors(hex_code)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_paint_colors_brand_id ON paint_colors(brand_id)")
    
    conn.commit()
    print("Tables and indexes created successfully.")

    # 1. Parse data_thuvienmau.txt
    print("Parsing data_thuvienmau.txt...")
    if not os.path.exists(thuvien_path):
        print(f"Error: {thuvien_path} not found!")
        return

    with open(thuvien_path, "r", encoding="utf-8") as f:
        thuvien_content = f.read()

    # Split JSON blocks
    thuvien_content = thuvien_content.replace("\r\n", "\n")
    parts = thuvien_content.split("}\n{")
    blocks = []
    for i, p in enumerate(parts):
        if i == 0:
            blocks.append(p + "}")
        elif i == len(parts) - 1:
            blocks.append("{" + p)
        else:
            blocks.append("{" + p + "}")

    all_collections = []
    for idx, b in enumerate(blocks):
        try:
            data = json.loads(b)
            collections = data.get("collections", []) or data.get("data", {}).get("collections", [])
            all_collections.extend(collections)
        except Exception as e:
            # print(f"Error parsing block {idx}: {e}")
            pass

    print(f"Found {len(all_collections)} raw collections.")

    # Deduplicate and process data
    project_types = {}
    collections_to_insert = []
    layers_to_insert = []

    for col in all_collections:
        col_id = str(col.get("id"))
        if not col_id:
            continue

        # Extract project type
        pt = col.get("project_type")
        pt_id = None
        if pt and "id" in pt:
            pt_id = pt["id"]
            if pt_id not in project_types:
                project_types[pt_id] = {
                    "id": pt_id,
                    "name": pt.get("name"),
                    "slug": pt.get("slug")
                }

        # Save collection details
        collections_to_insert.append((
            col_id,
            col.get("name"),
            col.get("description"),
            col.get("number_of_floors"),
            col.get("number_of_facades"),
            pt_id
        ))

        # Save layers
        layers = col.get("layers", [])
        for lay in layers:
            lay_id = str(lay.get("id"))
            if not lay_id:
                continue
            
            # Extract nested imageFile
            img_file = lay.get("imageFile") or {}
            img_url = img_file.get("url") or lay.get("image_url")
            img_path = img_file.get("path") or ""
            img_mime = img_file.get("mimeType") or "image/webp"

            # Parse visible as boolean -> int
            is_visible = 1 if lay.get("visible", True) else 0
            
            layers_to_insert.append((
                lay_id,
                col_id,
                lay.get("name"),
                img_url,
                img_path,
                img_mime,
                lay.get("layer_type"),
                lay.get("layer_type_display"),
                lay.get("zIndex", lay.get("z_index", 0)),
                lay.get("opacity", 1.0),
                is_visible
            ))

    # Insert project types
    for pt in project_types.values():
        cursor.execute("INSERT OR IGNORE INTO project_types (id, name, slug) VALUES (?, ?, ?)", (pt["id"], pt["name"], pt["slug"]))
    print(f"Inserted {len(project_types)} project types.")

    # Insert collections
    cursor.executemany("""
        INSERT OR REPLACE INTO collections (id, name, description, number_of_floors, number_of_facades, project_type_id)
        VALUES (?, ?, ?, ?, ?, ?)
    """, collections_to_insert)
    print(f"Inserted {len(collections_to_insert)} collections.")

    # Insert layers
    cursor.executemany("""
        INSERT OR REPLACE INTO layers (
            id, collection_id, name, image_url, image_path, image_mime_type, 
            layer_type, layer_type_display, z_index, opacity, visible
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, layers_to_insert)
    print(f"Inserted {len(layers_to_insert)} layers.")

    # 2. Parse mauson.txt
    print("Parsing mauson.txt...")
    if not os.path.exists(mauson_path):
        print(f"Error: {mauson_path} not found!")
        return

    with open(mauson_path, "r", encoding="utf-8") as f:
        mauson_content = f.read()

    mauson_content = mauson_content.replace("\r\n", "\n")
    parts = mauson_content.split("}\n{")
    color_blocks = []
    for i, p in enumerate(parts):
        if i == 0:
            color_blocks.append(p + "}")
        elif i == len(parts) - 1:
            color_blocks.append("{" + p)
        else:
            color_blocks.append("{" + p + "}")

    all_colors = []
    for idx, cb in enumerate(color_blocks):
        try:
            data = json.loads(cb)
            colors = data.get("data", {}).get("colors", []) or data.get("colors", [])
            all_colors.extend(colors)
        except Exception as e:
            # print(f"Error parsing color block {idx}: {e}")
            pass

    print(f"Found {len(all_colors)} raw paint colors.")

    brands = {}
    colors_to_insert = []

    for col_data in all_colors:
        color_id = col_data.get("id")
        if not color_id:
            continue

        brand_id = col_data.get("brand_id")
        brand_name = col_data.get("brand_name") or (col_data.get("brand", {}).get("name") if isinstance(col_data.get("brand"), dict) else col_data.get("brand_name", "Unknown"))

        if brand_id:
            if brand_id not in brands:
                brands[brand_id] = brand_name

        colors_to_insert.append((
            color_id,
            brand_id,
            col_data.get("name"),
            col_data.get("paint_code"),
            col_data.get("hex_code"),
            col_data.get("category"),
            col_data.get("finish"),
            col_data.get("coverage"),
            col_data.get("description")
        ))

    # Insert brands
    for bid, bname in brands.items():
        cursor.execute("INSERT OR IGNORE INTO brands (id, name) VALUES (?, ?)", (bid, bname))
    print(f"Inserted {len(brands)} paint brands.")

    # Insert paint colors
    cursor.executemany("""
        INSERT OR REPLACE INTO paint_colors (id, brand_id, name, paint_code, hex_code, category, finish, coverage, description)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, colors_to_insert)
    print(f"Inserted {len(colors_to_insert)} paint colors.")

    conn.commit()
    conn.close()
    print("Database seeding completed successfully.")

if __name__ == "__main__":
    seed_database()
