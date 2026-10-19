import math
from flask import Flask, render_template, request

app = Flask(__name__)

LONGUEUR_MAX = 50
TOUCHES_ECRAN = set("0123456789.+-*/()^")


# ---------- 1. Outils de calcul ----------

def decouper(expression):
    """Transforme "12+3*(2-1)" en [12.0, "+", 3.0, "*", "(", 2.0, "-", 1.0, ")"]."""
    elements = []
    nombre = ""
    for caractere in expression:
        if caractere in "0123456789.":
            nombre = nombre + caractere
        elif caractere == "-" and nombre == "" and (
                elements == [] or elements[-1] in ("+", "-", "*", "/", "(", "^")):
            nombre = "-"          # ici le "-" est le signe d'un nombre négatif
        elif caractere in "+-*/()^":
            if nombre != "":
                elements.append(float(nombre))
                nombre = ""
            elements.append(caractere)
        else:
            raise ValueError
    if nombre != "":
        elements.append(float(nombre))
    return elements


def verifier(elements):
    """Une liste valide alterne : nombre, opérateur, nombre, opérateur, ..., nombre."""
    if len(elements) % 2 == 0:
        raise ValueError
    for i in range(len(elements)):
        if i % 2 == 0 and not isinstance(elements[i], float):
            raise ValueError
        if i % 2 == 1 and not isinstance(elements[i], str):
            raise ValueError


def calculer(elements):
    """Calcule une liste SANS parenthèses : d'abord ^, puis * et /, puis + et -."""
    verifier(elements)

    # NOUVEAU - Première passe : ^ (de droite à gauche, car 2^3^2 = 2^(3^2))
    i = len(elements) - 2
    while i >= 1:
        if elements[i] == "^":
            resultat = elements[i - 1] ** elements[i + 1]
            if isinstance(resultat, complex):     # ex : (-8)^0.5 donne un nombre complexe
                raise ValueError
            elements[i - 1:i + 2] = [resultat]
        i = i - 2

    # Deuxième passe : * et /
    i = 0
    while i < len(elements):
        if elements[i] == "*" or elements[i] == "/":
            gauche = elements[i - 1]
            droite = elements[i + 1]
            if elements[i] == "*":
                resultat = gauche * droite
            else:
                resultat = gauche / droite
            elements[i - 1:i + 2] = [resultat]
        else:
            i = i + 1

    # Troisième passe : + et -, de gauche à droite
    total = elements[0]
    i = 1
    while i < len(elements):
        if elements[i] == "+":
            total = total + elements[i + 1]
        else:
            total = total - elements[i + 1]
        i = i + 2
    return total


def resoudre_parentheses(elements):
    """Remplace chaque groupe (...) par son résultat, en commençant par le plus intérieur."""
    while "(" in elements or ")" in elements:
        fin = elements.index(")")        # première ")" : elle ferme le groupe le plus intérieur
        debut = fin - 1
        while debut >= 0 and elements[debut] != "(":
            debut = debut - 1            # on remonte jusqu'à la "(" qui lui correspond
        if debut < 0:
            raise ValueError
        interieur = elements[debut + 1:fin]
        elements[debut:fin + 1] = [calculer(interieur)]
    return elements


def valeur(expression):
    """Texte -> nombre. Lève ValueError, ZeroDivisionError ou OverflowError si l'expression est invalide."""
    return calculer(resoudre_parentheses(decouper(expression)))


# ---------- 2. Outils d'affichage et de sécurité ----------

def formater(nombre):
    """18.0 -> "18", 2.5 -> "2.5", 0.30000000000000004 -> "0.3"."""
    if not math.isfinite(nombre):        # NOUVEAU : refuse "inf" et "nan"
        raise ValueError
    nombre = round(nombre, 10)
    if abs(nombre) < 1e15 and nombre == int(nombre):
        nombre = int(nombre)
    return str(nombre)


def nettoyer_memoire(texte):
    """La mémoire vient du navigateur, donc on ne lui fait pas confiance."""
    try:
        nombre = float(texte)
    except ValueError:
        return ""
    if not math.isfinite(nombre):
        return ""
    return formater(nombre)


def ajouter(expression, texte):
    if len(expression) + len(texte) > LONGUEUR_MAX:
        return expression
    return expression + texte


# ---------- 3. Logique des touches ----------

def traiter_touche(expression, memoire, touche):
    """Reçoit l'état actuel et la touche cliquée, renvoie (nouvelle expression, nouvelle mémoire)."""
    if expression == "Erreur":
        expression = ""

    if touche == "AC":
        return "", memoire

    if touche == "Delete":
        return expression[:-1], memoire

    if touche == "=":
        if expression == "":
            return "", memoire
        try:
            resultat = formater(valeur(expression))
        except (ValueError, ZeroDivisionError, OverflowError):    # NOUVEAU : OverflowError
            return "Erreur", memoire
        if len(resultat) > LONGUEUR_MAX:
            return "Erreur", memoire
        return resultat, memoire

    if touche == "MC":
        return expression, ""

    if touche == "MR":
        if memoire == "":
            return expression, memoire
        if memoire.startswith("-"):
            return ajouter(expression, "(" + memoire + ")"), memoire
        return ajouter(expression, memoire), memoire

    if touche == "M+" or touche == "M-":
        if expression == "":
            return expression, memoire
        try:
            nombre = valeur(expression)
        except (ValueError, ZeroDivisionError, OverflowError):    # NOUVEAU : OverflowError
            return "Erreur", memoire
        if not math.isfinite(nombre):                             # NOUVEAU : résultat infini
            return "Erreur", memoire
        actuel = float(memoire) if memoire != "" else 0.0
        if touche == "M+":
            actuel = actuel + nombre
        else:
            actuel = actuel - nombre
        return expression, nettoyer_memoire(str(actuel))

    if touche in TOUCHES_ECRAN:
        return ajouter(expression, touche), memoire

    return expression, memoire           # touche inconnue (%) : on ne fait rien


# ---------- 4. Route ----------

@app.route("/", methods=["GET", "POST"])
def accueil():
    expression = ""
    memoire = ""
    if request.method == "POST":
        expression = request.form.get("expression", "")[:LONGUEUR_MAX]
        memoire = nettoyer_memoire(request.form.get("memoire", ""))
        touche = request.form.get("touche", "")
        expression, memoire = traiter_touche(expression, memoire, touche)
    return render_template("index.html", expression=expression, memoire=memoire)


if __name__ == "__main__":
    app.run(debug=True)