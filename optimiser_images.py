import argparse            # Lire les arguments du terminal
import io                  # BytesIO : un "fichier" qui vit dans la mémoire, pas sur le disque
from pathlib import Path   # Manipuler les chemins de fichiers

from PIL import Image, ImageOps    # Image : ouvrir/modifier ; ImageOps : outils (orientation...)


EXTENSIONS = {".jpg", ".jpeg", ".png"}



def lisible(octets):
    """Transforme 1536000 en '1.5 Mo'."""
    for unite in ("o", "Ko", "Mo"):
        if octets < 1024:
            return f"{octets:.1f} {unite}"
        octets /= 1024
    return f"{octets:.1f} Go"


def destination_libre(chemin):
    """photo.webp existe déjà ? On essaie photo_1.webp, photo_2.webp..."""
    original = chemin
    numero = 1
    while chemin.exists():
        chemin = original.with_name(f"{original.stem}_{numero}{original.suffix}")
        numero += 1
    return chemin



def optimiser_en_memoire(chemin, largeur_max, qualite):
    """Renvoie le contenu WebP (en octets) de l'image redimensionnée. N'écrit rien sur le disque."""
    with Image.open(chemin) as image:
        # Les photos de téléphone gardent leur orientation dans l'EXIF : sans cette ligne,
        # elles ressortiraient couchées. exif_transpose les remet à l'endroit.
        image = ImageOps.exif_transpose(image)

        # thumbnail réduit l'image pour qu'elle tienne dans (largeur_max, 100000),
        # en gardant les proportions. Elle ne fait JAMAIS grossir une petite image.
        image.thumbnail((largeur_max, 100000), Image.Resampling.LANCZOS)

        # Si l'image a de la transparence (logo PNG...), on la garde. Sinon, on simplifie.
        a_transparence = image.mode in ("RGBA", "LA") or "transparency" in image.info
        image = image.convert("RGBA" if a_transparence else "RGB")

        # On "enregistre" dans la mémoire (BytesIO) pour connaître la taille obtenue.
        # Les métadonnées (position GPS, appareil...) ne sont pas recopiées : c'est voulu.
        tampon = io.BytesIO()
        image.save(tampon, format="WEBP", quality=qualite, method=6)
        return tampon.getvalue()

def preparer_pour_reseau(chemin, taille, qualite):
    """Recadre l'image à la taille exacte du réseau et renvoie du JPEG."""
    with Image.open(chemin) as image:
        image = ImageOps.exif_transpose(image)
        # fit = redimensionne PUIS recadre au centre pour obtenir la taille exacte
        image = ImageOps.fit(image, taille, Image.Resampling.LANCZOS)
        # Le JPEG ne gère pas la transparence : on la remplace par un fond blanc
        if image.mode in ("RGBA", "LA") or "transparency" in image.info:
            image = image.convert("RGBA")
            fond = Image.new("RGB", image.size, "white")
            fond.paste(image, mask=image.split()[-1])
            image = fond
        else:
            image = image.convert("RGB")
        tampon = io.BytesIO()
        image.save(tampon, format="JPEG", quality=qualite, optimize=True)
        return tampon.getvalue()

def main():
    parser = argparse.ArgumentParser(description="Optimise des images pour le web (WebP).")
    parser.add_argument("dossier", help="Dossier contenant les images")
    parser.add_argument("--sortie",
                        help="Dossier de sortie (par défaut : <dossier>_webp, à côté du dossier source)")
    parser.add_argument("--largeur", type=int, default=1920,
                        help="Largeur maximale en pixels (défaut : 1920)")
    parser.add_argument("--qualite", type=int, default=80,
                        help="Qualité WebP de 1 à 100 (défaut : 80)")
    parser.add_argument("--appliquer", action="store_true",
                        help="Crée vraiment les images optimisées (sinon : simulation)")
    args = parser.parse_args()


    dossier = Path(args.dossier)
    if not dossier.is_dir():
        print("Dossier introuvable.")
        return
    if not 1 <= args.qualite <= 100:
        print("La qualité doit être comprise entre 1 et 100.")
        return
    if args.largeur < 100:
        print("La largeur maximale doit être d'au moins 100 pixels.")
        return

    # Dossier de sortie : par défaut, un dossier "voisin" nommé <dossier>_webp
    sortie = Path(args.sortie) if args.sortie else dossier.parent / f"{dossier.name}_webp"
    if sortie.resolve() == dossier.resolve():
        print("Le dossier de sortie doit être différent du dossier source.")
        return

    # --- Liste des images ---
    fichiers = sorted(
        f for f in dossier.iterdir()
        if f.is_file() and f.suffix.lower() in EXTENSIONS
    )
    if not fichiers:
        print("Aucune image (.jpg, .jpeg, .png) trouvée dans ce dossier.")
        return

    print("MODE :", "ÉCRITURE RÉELLE" if args.appliquer else "SIMULATION (aucun fichier écrit)")
    print(f"Réglages : largeur max {args.largeur} px, qualité {args.qualite}")
    print()

    # --- Traitement ---
    total_avant = 0
    total_apres = 0
    optimisees = 0
    ignorees = 0
    erreurs = 0

    for fichier in fichiers:
        avant = fichier.stat().st_size
        # Nom raccourci pour garder le tableau aligné
        nom = fichier.name if len(fichier.name) <= 32 else fichier.name[:29] + "..."

        try:
            donnees = optimiser_en_memoire(fichier, args.largeur, args.qualite)
        except Exception as erreur:
            print(f"{nom:<32}  ERREUR : {erreur}")
            erreurs += 1
            continue                       # on passe à l'image suivante

        apres = len(donnees)

        # Si le résultat est plus lourd que l'original (image déjà très légère),
        # inutile de la convertir : on l'ignore.
        if apres >= avant:
            print(f"{nom:<32}  {lisible(avant):>9}  ignorée (déjà légère)")
            ignorees += 1
            continue

        gain = 100 * (avant - apres) / avant
        print(f"{nom:<32}  {lisible(avant):>9} -> {lisible(apres):>9}   -{gain:.0f} %")
        total_avant += avant
        total_apres += apres
        optimisees += 1

        if args.appliquer:
            cible = destination_libre(sortie / (fichier.stem + ".webp"))
            cible.parent.mkdir(parents=True, exist_ok=True)
            cible.write_bytes(donnees)     # on écrit les octets WebP déjà calculés

    # --- Résumé ---
    print()
    print(f"{len(fichiers)} image(s) : {optimisees} optimisée(s), {ignorees} ignorée(s), {erreurs} erreur(s).")
    if optimisees:
        economie = total_avant - total_apres
        pourcentage = 100 * economie / total_avant
        print(f"Poids total : {lisible(total_avant)} -> {lisible(total_apres)}  "
              f"(économie : {lisible(economie)}, soit {pourcentage:.0f} %)")
    if args.appliquer:
        print(f"Images créées dans : {sortie}")
    else:
        print("Simulation terminée. Ajoute --appliquer pour créer les images.")

if __name__ == "__main__":
    main()