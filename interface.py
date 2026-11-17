# ============================================================
# interface.py : ÉCRAN de l'optimiseur (les boutons ne font rien pour l'instant).
# Deux modes au choix :
#   - "Réduire"  : convertit en WebP, pour un SITE WEB (largeur max libre)
#   - "Réseau"   : redimensionne à la taille EXACTE d'un réseau social (JPEG)
# Les dimensions des réseaux ne sont PAS ici : elles sont dans formats.py
# ============================================================

import tkinter as tk
from tkinter import ttk

from formats import FORMATS    # la liste des dimensions (voir formats.py pour les modifier)


class Application:
    def __init__(self, fenetre):
        fenetre.title("Optimiseur d'images")
        fenetre.geometry("780x720")
        fenetre.configure(bg="#F4F5F7")

        tk.Label(fenetre, text="OPTIMISEUR D'IMAGES",
                 font=("Arial", 18, "bold"), bg="#F4F5F7").pack(pady=(15, 5))

        # ---------- LES DEUX CHAMPS DE DOSSIER ----------
        self.entree_source = self.ligne_dossier(fenetre, "1. Dossier des images")
        self.entree_sortie = self.ligne_dossier(fenetre, "2. Dossier de sortie")

        # ---------- LE CHOIX DU MODE ----------
        tk.Label(fenetre, text="3. Que veux-tu faire ?", font=("Arial", 11, "bold"),
                 bg="#F4F5F7").pack(anchor="w", padx=35, pady=(12, 0))

        # StringVar = une variable texte qui mémorise le mode choisi : "reduire" ou "reseau".
        # Les deux boutons radio partagent la même variable : un seul peut être coché.
        self.mode = tk.StringVar(value="reduire")

        cadre_modes = tk.Frame(fenetre, bg="#F4F5F7")
        cadre_modes.pack(fill="x", padx=35, pady=4)

        # --- Ligne 1 : RÉDUIRE (WebP, pour le web) ---
        tk.Radiobutton(cadre_modes, text="Réduire (WebP, pour un site web)",
                       variable=self.mode, value="reduire", bg="#F4F5F7",
                       command=self.changer_mode).grid(row=0, column=0, sticky="w")
        tk.Label(cadre_modes, text="Largeur max (px) :", bg="#F4F5F7").grid(row=0, column=1, padx=(20, 5))
        self.largeur = ttk.Spinbox(cadre_modes, from_=200, to=8000, increment=100, width=8)
        self.largeur.set(1920)
        self.largeur.grid(row=0, column=2)

        # --- Ligne 2 : RÉSEAU (JPEG, taille exacte) ---
        tk.Radiobutton(cadre_modes, text="Redimensionner pour un réseau (JPEG)",
                       variable=self.mode, value="reseau", bg="#F4F5F7",
                       command=self.changer_mode).grid(row=1, column=0, sticky="w", pady=(6, 0))
        # Combobox = liste déroulante. Les choix viennent de formats.py.
        self.format = ttk.Combobox(cadre_modes, values=list(FORMATS), state="readonly", width=26)
        self.format.current(0)
        self.format.bind("<<ComboboxSelected>>", self.changer_mode)
        self.format.grid(row=1, column=1, columnspan=2, padx=(20, 0), pady=(6, 0), sticky="w")

        # Texte qui affiche la taille exacte du format choisi
        self.info_format = tk.Label(fenetre, bg="#F4F5F7", fg="#2563EB", font=("Arial", 10, "bold"))
        self.info_format.pack(anchor="w", padx=35)

        # Avertissement demandé : les tailles changent
        tk.Label(fenetre, bg="#F4F5F7", fg="#B45309", font=("Arial", 9), justify="left",
                 text="⚠ Les dimensions des réseaux sociaux changent souvent. "
                      "Pour les corriger : fichier formats.py."
                 ).pack(anchor="w", padx=35, pady=(0, 4))

        # ---------- LA QUALITÉ (commune aux deux modes) ----------
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
                                command=self.pas_encore)
        self.bouton.pack(fill="x", padx=35, pady=12, ipady=8)

        # ---------- LA BARRE DE PROGRESSION ----------
        self.progression = ttk.Progressbar(fenetre, mode="determinate")
        self.progression.pack(fill="x", padx=35)
        self.progression["value"] = 35        # TEMPORAIRE

        # ---------- LE TABLEAU AVANT / APRÈS ----------
        cadre_tableau = tk.Frame(fenetre)
        cadre_tableau.pack(fill="both", expand=True, padx=35, pady=10)
        colonnes = ("nom", "avant", "apres", "gain")
        self.tableau = ttk.Treeview(cadre_tableau, columns=colonnes, show="headings", height=8)
        for colonne, titre, largeur in (("nom", "Image", 300), ("avant", "Avant", 90),
                                        ("apres", "Après", 90), ("gain", "Gain", 190)):
            self.tableau.heading(colonne, text=titre)
            self.tableau.column(colonne, width=largeur, anchor="w")
        defilement = ttk.Scrollbar(cadre_tableau, orient="vertical", command=self.tableau.yview)
        self.tableau.configure(yscrollcommand=defilement.set)
        self.tableau.pack(side="left", fill="both", expand=True)
        defilement.pack(side="right", fill="y")
        self.tableau.insert("", "end", values=("exemple.jpg", "4.1 Mo", "420 Ko", "-90 %"))

        tk.Label(fenetre, text="En attente", bg="#F4F5F7", fg="#666666",
                 font=("Arial", 10)).pack(pady=(0, 12))

        self.changer_mode()    # applique l'état de départ (mode "Réduire")

    def ligne_dossier(self, fenetre, titre):
        """Crée un titre, un champ de texte et un bouton Parcourir. Renvoie le champ."""
        tk.Label(fenetre, text=titre, font=("Arial", 11, "bold"),
                 bg="#F4F5F7").pack(anchor="w", padx=35, pady=(12, 0))
        cadre = tk.Frame(fenetre, bg="#F4F5F7")
        cadre.pack(fill="x", padx=35, pady=4)
        entree = tk.Entry(cadre, font=("Arial", 10))
        entree.pack(side="left", fill="x", expand=True, ipady=5)
        tk.Button(cadre, text="Parcourir", command=self.pas_encore).pack(side="right", padx=(8, 0))
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
            largeur, hauteur = FORMATS[self.format.get()]    # dimensions lues dans formats.py
            self.info_format.config(text=f"Sortie : {largeur} x {hauteur} px, JPEG, recadré au centre")

    def pas_encore(self):
        print("Ce bouton n'est pas encore branché.")


def main():
    fenetre = tk.Tk()
    Application(fenetre)
    fenetre.lift()
    fenetre.attributes("-topmost", True)
    fenetre.after(500, lambda: fenetre.attributes("-topmost", False))
    fenetre.mainloop()


if __name__ == "__main__":
    main()