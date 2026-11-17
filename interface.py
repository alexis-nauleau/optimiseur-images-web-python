# ============================================================
# interface.py : l'optimiseur d'images avec ses boutons branchés.
# Deux modes :
#   - "Réduire" : WebP, pour un site web (largeur max libre)
#   - "Réseau"  : JPEG, taille exacte d'un réseau social (voir formats.py)
# ============================================================

import os                         # pour ouvrir le dossier de sortie dans l'Explorateur
import queue                      # la "boîte aux lettres" entre le thread et la fenêtre
import threading                  # pour travailler en arrière-plan
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from formats import FORMATS       # dimensions des réseaux (à modifier dans formats.py)
from optimiser_images import (EXTENSIONS, destination_libre, lisible,
                              optimiser_en_memoire, preparer_pour_reseau)


class Application:
    def __init__(self, fenetre):
        self.fenetre = fenetre
        self.file = queue.Queue()      # les messages envoyés par le thread
        self.en_cours = False          # True pendant qu'une optimisation tourne
        self.dossier_ecrit = None      # dossier où l'on a écrit (pour le bouton "Ouvrir")

        fenetre.title("Optimiseur d'images")
        fenetre.geometry("780x740")
        fenetre.configure(bg="#F4F5F7")

        tk.Label(fenetre, text="OPTIMISEUR D'IMAGES",
                 font=("Arial", 18, "bold"), bg="#F4F5F7").pack(pady=(15, 5))

        # ---------- LES DEUX CHAMPS DE DOSSIER ----------
        # Chaque bouton "Parcourir" reçoit le champ qu'il doit remplir.
        self.entree_source = self.ligne_dossier(fenetre, "1. Dossier des images")
        self.entree_sortie = self.ligne_dossier(fenetre, "2. Dossier de sortie (vide = automatique)")

        # ---------- LE CHOIX DU MODE ----------
        tk.Label(fenetre, text="3. Que veux-tu faire ?", font=("Arial", 11, "bold"),
                 bg="#F4F5F7").pack(anchor="w", padx=35, pady=(12, 0))
        self.mode = tk.StringVar(value="reduire")      # "reduire" ou "reseau"

        cadre_modes = tk.Frame(fenetre, bg="#F4F5F7")
        cadre_modes.pack(fill="x", padx=35, pady=4)

        tk.Radiobutton(cadre_modes, text="Réduire (WebP, pour un site web)",
                       variable=self.mode, value="reduire", bg="#F4F5F7",
                       command=self.changer_mode).grid(row=0, column=0, sticky="w")
        tk.Label(cadre_modes, text="Largeur max (px) :", bg="#F4F5F7").grid(row=0, column=1, padx=(20, 5))
        self.largeur = ttk.Spinbox(cadre_modes, from_=200, to=8000, increment=100, width=8)
        self.largeur.set(1920)
        self.largeur.grid(row=0, column=2)

        tk.Radiobutton(cadre_modes, text="Redimensionner pour un réseau (JPEG)",
                       variable=self.mode, value="reseau", bg="#F4F5F7",
                       command=self.changer_mode).grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.format = ttk.Combobox(cadre_modes, values=list(FORMATS), state="readonly", width=26)
        self.format.current(0)
        self.format.bind("<<ComboboxSelected>>", self.changer_mode)
        self.format.grid(row=1, column=1, columnspan=2, padx=(20, 0), pady=(6, 0), sticky="w")

        self.info_format = tk.Label(fenetre, bg="#F4F5F7", fg="#2563EB", font=("Arial", 10, "bold"))
        self.info_format.pack(anchor="w", padx=35)
        tk.Label(fenetre, bg="#F4F5F7", fg="#B45309", font=("Arial", 9),
                 text="⚠ Les dimensions des réseaux sociaux changent souvent. "
                      "Pour les corriger : fichier formats.py."
                 ).pack(anchor="w", padx=35, pady=(0, 4))

        # ---------- LA QUALITÉ + L'APERÇU ----------
        cadre_qualite = tk.Frame(fenetre, bg="#F4F5F7")
        cadre_qualite.pack(fill="x", padx=35, pady=(6, 0))
        tk.Label(cadre_qualite, text="Qualité :", bg="#F4F5F7").pack(side="left")
        self.qualite = tk.Scale(cadre_qualite, from_=1, to=100, orient="horizontal",
                                length=220, bg="#F4F5F7", highlightthickness=0)
        self.qualite.set(80)
        self.qualite.pack(side="left", padx=8)

        self.apercu = tk.BooleanVar(value=False)
        tk.Checkbutton(fenetre, variable=self.apercu, bg="#F4F5F7",
                       text="Aperçu seulement (calcule les tailles, n'écrit aucun fichier)"
                       ).pack(anchor="w", padx=35, pady=(4, 0))

        # ---------- LE BOUTON PRINCIPAL ----------
        self.bouton = tk.Button(fenetre, text="LANCER", font=("Arial", 12, "bold"),
                                bg="#2563EB", fg="white", relief="flat", cursor="hand2",
                                command=self.lancer)          # <-- branché !
        self.bouton.pack(fill="x", padx=35, pady=12, ipady=8)

        # ---------- LA BARRE DE PROGRESSION ----------
        self.progression = ttk.Progressbar(fenetre, mode="determinate")
        self.progression.pack(fill="x", padx=35)

        # ---------- LE TABLEAU AVANT / APRÈS ----------
        cadre_tableau = tk.Frame(fenetre)
        cadre_tableau.pack(fill="both", expand=True, padx=35, pady=10)
        colonnes = ("nom", "avant", "apres", "gain")
        self.tableau = ttk.Treeview(cadre_tableau, columns=colonnes, show="headings", height=8)
        for colonne, titre, largeur in (("nom", "Image", 300), ("avant", "Avant", 90),
                                        ("apres", "Après", 90), ("gain", "Gain", 190)):
            self.tableau.heading(colonne, text=titre)
            self.tableau.column(colonne, width=largeur, anchor="w")
        # Les "tags" colorent certaines lignes
        self.tableau.tag_configure("ignoree", foreground="#999999")
        self.tableau.tag_configure("erreur", foreground="#DC2626")
        defilement = ttk.Scrollbar(cadre_tableau, orient="vertical", command=self.tableau.yview)
        self.tableau.configure(yscrollcommand=defilement.set)
        self.tableau.pack(side="left", fill="both", expand=True)
        defilement.pack(side="right", fill="y")

        # ---------- LE RÉSUMÉ + OUVRIR LE DOSSIER ----------
        self.resume = tk.Label(fenetre, text="En attente", bg="#F4F5F7", fg="#666666",
                               font=("Arial", 10, "bold"))
        self.resume.pack()
        self.bouton_ouvrir = tk.Button(fenetre, text="Ouvrir le dossier de sortie",
                                       state="disabled", command=self.ouvrir_sortie)
        self.bouton_ouvrir.pack(pady=(4, 12))

        self.changer_mode()

    # ================== CONSTRUCTION ==================
    def ligne_dossier(self, fenetre, titre):
        """Titre + champ + bouton Parcourir. Renvoie le champ."""
        tk.Label(fenetre, text=titre, font=("Arial", 11, "bold"),
                 bg="#F4F5F7").pack(anchor="w", padx=35, pady=(12, 0))
        cadre = tk.Frame(fenetre, bg="#F4F5F7")
        cadre.pack(fill="x", padx=35, pady=4)
        entree = tk.Entry(cadre, font=("Arial", 10))
        entree.pack(side="left", fill="x", expand=True, ipady=5)
        # lambda : on "emballe" l'appel pour pouvoir lui passer le champ à remplir
        tk.Button(cadre, text="Parcourir",
                  command=lambda: self.choisir(entree)).pack(side="right", padx=(8, 0))
        return entree

    def changer_mode(self, evenement=None):
        """Active la ligne du mode choisi et grise l'autre."""
        if self.mode.get() == "reduire":
            self.largeur.configure(state="normal")
            self.format.configure(state="disabled")
            self.info_format.config(text="Sortie : WebP, proportions conservées")
        else:
            self.largeur.configure(state="disabled")
            self.format.configure(state="readonly")
            largeur, hauteur = FORMATS[self.format.get()]    # lu dans formats.py
            self.info_format.config(text=f"Sortie : {largeur} x {hauteur} px, JPEG, recadré au centre")

    # ================== LES BOUTONS ==================
    def choisir(self, entree):
        """Ouvre la fenêtre de choix de dossier et écrit le résultat dans le champ."""
        dossier = filedialog.askdirectory()
        if dossier:                          # vide si l'utilisateur annule
            entree.delete(0, "end")
            entree.insert(0, dossier)

    def ouvrir_sortie(self):
        if self.dossier_ecrit and self.dossier_ecrit.exists():
            os.startfile(self.dossier_ecrit)      # ouvre l'Explorateur Windows

    def lancer(self):
        """Lit l'écran, vérifie, puis démarre le travail en arrière-plan."""
        if self.en_cours:
            return

        # --- 1. Dossier source ---
        texte_source = self.entree_source.get().strip()
        if not texte_source or not Path(texte_source).is_dir():
            messagebox.showerror("Dossier introuvable", "Choisis un dossier d'images valide.")
            return
        source = Path(texte_source)

        # --- 2. Mode et réglages ---
        mode = self.mode.get()
        try:
            largeur = int(self.largeur.get())
        except ValueError:
            messagebox.showerror("Largeur invalide", "La largeur doit être un nombre.")
            return
        qualite = self.qualite.get()
        apercu = self.apercu.get()
        taille = FORMATS[self.format.get()]

        # --- 3. Dossier de sortie (automatique si vide) ---
        texte_sortie = self.entree_sortie.get().strip()
        if texte_sortie:
            sortie = Path(texte_sortie)
        else:
            suffixe = "_webp" if mode == "reduire" else "_reseau"
            sortie = source.parent / (source.name + suffixe)
            self.entree_sortie.insert(0, str(sortie))      # on l'affiche pour que ce soit clair

        # Sécurité : jamais écrire dans le dossier des originaux
        if sortie.resolve() == source.resolve():
            messagebox.showerror("Dossier de sortie", "Le dossier de sortie doit être différent du dossier source.")
            return

        # --- 4. On prépare l'écran ---
        self.tableau.delete(*self.tableau.get_children())     # vide le tableau
        self.progression["value"] = 0
        self.resume.config(text="Traitement en cours...")
        self.bouton.config(state="disabled", text="EN COURS...")
        self.bouton_ouvrir.config(state="disabled")
        self.dossier_ecrit = None
        self.en_cours = True

        # --- 5. On démarre le thread, puis on surveille sa boîte aux lettres ---
        # daemon=True : si on ferme la fenêtre, le thread s'arrête avec elle
        threading.Thread(target=self.travail, daemon=True,
                         args=(source, sortie, mode, largeur, qualite, apercu, taille)).start()
        self.surveiller()

    # ================== LE TRAVAIL (thread) ==================
    def travail(self, source, sortie, mode, largeur, qualite, apercu, taille):
        """Tourne en arrière-plan. NE TOUCHE JAMAIS aux widgets : il envoie des messages."""
        images = sorted(p for p in source.iterdir()
                        if p.is_file() and p.suffix.lower() in EXTENSIONS)
        self.file.put(("debut", len(images)))

        total_avant = total_apres = traitees = ignorees = erreurs = ecrites = 0

        for numero, chemin in enumerate(images, start=1):
            try:
                avant = chemin.stat().st_size
                if mode == "reduire":
                    donnees = optimiser_en_memoire(chemin, largeur, qualite)
                    extension = ".webp"
                else:
                    donnees = preparer_pour_reseau(chemin, taille, qualite)
                    extension = ".jpg"
                apres = len(donnees)

                if mode == "reduire" and apres >= avant:
                    # Le WebP serait plus lourd : on ne touche pas à cette image
                    ignorees += 1
                    self.file.put(("ligne", chemin.name, lisible(avant), "-",
                                   "Ignorée (déjà optimisée)", "ignoree"))
                else:
                    if not apercu:
                        sortie.mkdir(parents=True, exist_ok=True)
                        destination = destination_libre(sortie / (chemin.stem + extension))
                        destination.write_bytes(donnees)
                        ecrites += 1
                    traitees += 1
                    total_avant += avant
                    total_apres += apres
                    gain = (apres - avant) / avant * 100 if avant else 0
                    self.file.put(("ligne", chemin.name, lisible(avant), lisible(apres),
                                   f"{gain:+.0f} %", ""))
            except Exception as erreur:
                erreurs += 1
                self.file.put(("ligne", chemin.name, "-", "-", f"Erreur : {erreur}", "erreur"))

            self.file.put(("progression", numero))

        # --- Résumé final ---
        if traitees:
            gain_total = (total_apres - total_avant) / total_avant * 100 if total_avant else 0
            texte = f"{traitees} image(s) : {lisible(total_avant)} → {lisible(total_apres)} ({gain_total:+.0f} %)"
        else:
            texte = "Aucune image traitée"
        if ignorees:
            texte += f" · {ignorees} ignorée(s)"
        if erreurs:
            texte += f" · {erreurs} erreur(s)"
        if apercu:
            texte = "APERÇU, rien n'a été écrit. " + texte
        self.file.put(("termine", texte, sortie if ecrites else None))

    # ================== LA SURVEILLANCE (fenêtre) ==================
    def surveiller(self):
        """Lit la boîte aux lettres toutes les 100 ms et met l'écran à jour."""
        try:
            while True:
                message = self.file.get_nowait()      # lève queue.Empty s'il n'y a rien
                genre = message[0]

                if genre == "debut":
                    self.progression["maximum"] = max(message[1], 1)
                    if message[1] == 0:
                        self.resume.config(text="Aucune image JPG/PNG dans ce dossier")
                elif genre == "ligne":
                    _, nom, avant, apres, gain, tag = message
                    ligne = self.tableau.insert("", "end", values=(nom, avant, apres, gain),
                                                tags=(tag,) if tag else ())
                    self.tableau.see(ligne)             # fait défiler vers la dernière ligne
                elif genre == "progression":
                    self.progression["value"] = message[1]
                elif genre == "termine":
                    self.resume.config(text=message[1])
                    self.dossier_ecrit = message[2]
                    self.bouton.config(state="normal", text="LANCER")
                    if self.dossier_ecrit:
                        self.bouton_ouvrir.config(state="normal")
                    self.en_cours = False
        except queue.Empty:
            pass                                       # plus de message pour l'instant

        if self.en_cours:
            self.fenetre.after(100, self.surveiller)   # on revient dans 100 ms


def main():
    fenetre = tk.Tk()
    Application(fenetre)
    fenetre.lift()
    fenetre.attributes("-topmost", True)
    fenetre.after(500, lambda: fenetre.attributes("-topmost", False))
    fenetre.mainloop()


if __name__ == "__main__":
    main()