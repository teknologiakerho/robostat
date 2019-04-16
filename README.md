Robostat
========

Robostat on lasten ja nuorten robotiikkakilpailujen järjestämiseen ja tuomarointiin kehitetty järjestelmä. Robostat on alunperin kehitetty Innokas-robotiikkatapahtumaa varten, mutta sitä käytetään myös pienemissä aluekohtaisissa tapahtumissa.

Projektin rakenne
-----------------

 - **robostat-core** - Pisteiden laskenta ja tarkistus, komentorivityökalut pisteiden ja tietokannan käsittelyyn.
 - [robostat-web][1] - Web-käyttöliittymä ja HTTP-api.
 - [robostat-streamkit][2] - Lisätyökaluja ja scriptejä pääasiassa livestreamaukseen.

  [1]: https://github.com/teknologiakerho/robostat-web
  [2]: https://github.com/teknologiakerho/robostat-streamkit

Ominaisuudet
------------

 - Automaattinen pisteiden laskenta ja tarkistus
 - Aikataulujen tuonti ja vienti
 - Omien lajien määrittely, mukana tuki Innokas-robotiikkakilpailun lajeille
 - Joukkueiden sijoittaminen omien kriteerien mukaan
   * Esimerkiksi: eniten pisteitä lohkossa, eniten voittoja lohkossa
 - Lohkojen tulosten yhdistäminen omien kriteerien mukaan
   * Esimerkiksi: tanssissa summa tuomarien keskiarvoista haastattelu- ja esityskierroksilla
   * Esimerkiksi: parhaiden pisteiden voimaan jääminen pelastuksessa

Lajit
-----

Robostat tukee suoraan seuraavia virallisia Innokas-robotiikkakilpailun kisalajeja ja niiden yleisiä voittokriteerejä.

 - XSumo (Innokas- ja robomestari-säännöt)
 - Pelastus 1, 2, ja 3 (2019 pisteytys)
 - Tanssi ja teatteri (2019 pisteytys, vain pisteenlasku, ei web-käyttöliittymää tällä hetkellä).

Lisenssi
--------
Robostat on julkaistu MIT-lisenssillä.
