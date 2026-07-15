#!/bin/bash

# Abbrechen wenn createProject oder updateProject am Ende fehlschlagen damit cURL nicht läuft
#set -e

export LC_CTYPE=C.UTF-8


function createProject() {
  local base="/nfs/mtext/${linie}${umgebung}/serverSync"
  local dir="${base}/$1"

  echo "Frischer Checkout des Projektes $1"

  mkdir -p "${base}"
  cd "${base}" || return 1

  chmod u+w -R "${dir}" 2>/dev/null || true
  rm -rf -- "${dir}"

  svn checkout \
    --username="${usr}" \
    --password="${pass}" \
    -r "${REVISION}" \
    "https://itv-mtext-svn.en4920.de/${REPOS}/branches/${ART}/${RELEASE}_MText/$2" \
    "${dir}"
}

function updateProject() {
  cd "/nfs/mtext/${linie}${umgebung}/serverSync/$1" || return 1
  pwd
  echo "Update des Projektes $1"

  # minimaler Vorab-Cleanup gegen haengende SVN-Locks / abgebrochene Operationen
  svn cleanup

  # Normalfall: schnelles Update
  if svn update --username="${usr}" --password="${pass}" -r "${REVISION}"; then
    return 0
  fi

  echo "svn update fehlgeschlagen, versuche Bereinigung mit revert"

  # Reparaturpfad: lokale Aenderungen verwerfen
  svn cleanup || true
  svn revert -R .

  # Zweiter Versuch nach Bereinigung.
  svn update --username="${usr}" --password="${pass}" -r "${REVISION}"
}


function uploadHost() {

  echo "#!/usr/bin/env python3"                                                   >  $WORKSPACE/upload.py
  
  echo "import ftplib"                                                           >> $WORKSPACE/upload.py
  echo "session = ftplib.FTP('ize9.lbs-it.de', '${husr}', '${hpass}')"           >> $WORKSPACE/upload.py
  echo "file = open ('$1', 'rb')"                              					 >> $WORKSPACE/upload.py
  echo "session.storbinary(\"STOR 'IEA.LOMS.TONICZ($2)'\", file)"                >> $WORKSPACE/upload.py
  echo "file.close()"                                                            >> $WORKSPACE/upload.py
  echo "session.sendcmd('SITE FILETYPE=JES')"                                    >> $WORKSPACE/upload.py
  echo "jcl = open('$WORKSPACE/add.jcl', 'rb' )"                                 >> $WORKSPACE/upload.py
  echo "session.storlines(\"STOR LIT9028A\", jcl)"                               >> $WORKSPACE/upload.py
  echo "jcl.close()"                                                             >> $WORKSPACE/upload.py
  echo "session.quit()"                                                          >> $WORKSPACE/upload.py

  echo "//LIT9028A JOB (IE-00-TSO0-0000),'TONIC-SVN-UPLOAD',                     " >  $WORKSPACE/add.jcl
  echo "//         MSGCLASS=H,CLASS=L,REGION=256M,NOTIFY=&SYSUID                 " >> $WORKSPACE/add.jcl
  echo "//*-------------------------------------------------------------------+  " >> $WORKSPACE/add.jcl

  echo "//* =============================================================== *//  " >> $WORKSPACE/add.jcl
  echo "//* IMPORT UND REGISTRIERUNG EINES TONIC-ELEMENTS IN CODE PIPELINE  *//  " >> $WORKSPACE/add.jcl
  echo "//* =============================================================== *//  " >> $WORKSPACE/add.jcl
  echo "//*                                                                      " >> $WORKSPACE/add.jcl
  echo "//* --------------------------------------------------------------- *//  " >> $WORKSPACE/add.jcl
  echo "//* DIESER JOB BESTEHT AUS 2 STEPS.                                 *//  " >> $WORKSPACE/add.jcl
  echo "//*                                                                 *//  " >> $WORKSPACE/add.jcl
  echo "//*   NR. STEPNAME   PROGRAMM   FUNKTION                            *//  " >> $WORKSPACE/add.jcl
  echo "//*   -----------------------------------------------------------   *//  " >> $WORKSPACE/add.jcl
  echo "//*   1   MBRCOPY    IEBCOPY    KOPIEREN DES PHYSISCHEN MEMBERS     *//  " >> $WORKSPACE/add.jcl
  echo "//*                             IN DIE EMPFANGSDATEI VON CP         *//  " >> $WORKSPACE/add.jcl
  echo "//*   2   MBRADD     WZZRCJOB   REGISTRIEREN DER METADATEN ZUM      *//  " >> $WORKSPACE/add.jcl
  echo "//*                             NEUEN ELEMENT IM ZIEL-LEVEL         *//  " >> $WORKSPACE/add.jcl
  echo "//* --------------------------------------------------------------- *//  " >> $WORKSPACE/add.jcl
  echo "//*                                                                      " >> $WORKSPACE/add.jcl
  echo "//* --------------------------------------------------------------- *//  " >> $WORKSPACE/add.jcl
  echo "//* COPY MEMBER INTO CODE PIPELINE PDS                              *//  " >> $WORKSPACE/add.jcl
  echo "//* --------------------------------------------------------------- *//  " >> $WORKSPACE/add.jcl
  echo "//MBRCOPY  EXEC PGM=IEBCOPY                                              " >> $WORKSPACE/add.jcl
  echo "//SYSPRINT DD SYSOUT=*                                                   " >> $WORKSPACE/add.jcl
  echo "//* QUELLDATEI ------------.                                             " >> $WORKSPACE/add.jcl
  echo "//*                        !                                             " >> $WORKSPACE/add.jcl
  echo "//*                        V                                             " >> $WORKSPACE/add.jcl
  echo "//COPYIN   DD DISP=SHR,DSN=IEA.LOMS.TONICZ                               " >> $WORKSPACE/add.jcl
  echo "//* ZIELDATEI  ------------.       .------------- INSTANZ T=TEST/P=PROD  " >> $WORKSPACE/add.jcl
  echo "//*                        !       ! .----------- STREAM (BOAS)          " >> $WORKSPACE/add.jcl
  echo "//*                        !       ! !    .------ LEVEL  (FKTE/JURP)     " >> $WORKSPACE/add.jcl
  echo "//*                        !       ! !    !    .- TYPE   (TONICZ)        " >> $WORKSPACE/add.jcl
  echo "//*                        !       ! !    !    !                         " >> $WORKSPACE/add.jcl
  echo "//*                        V       V V    V    V                         " >> $WORKSPACE/add.jcl
  echo "//COPYOUT  DD DISP=SHR,DSN=IEA.ISPW${ISPW}.BOAS.${LEVEL}.TONICZ          " >> $WORKSPACE/add.jcl
  echo "//SYSIN    DD *                                                          " >> $WORKSPACE/add.jcl
  echo "  COPYMOD OUTDD=COPYOUT,INDD=COPYIN,LIST=YES                             " >> $WORKSPACE/add.jcl
  echo "  SELECT MEMBER=(($2,,R))                                                " >> $WORKSPACE/add.jcl
  echo "/*                                                                       " >> $WORKSPACE/add.jcl
  echo "//*               !                                                      " >> $WORKSPACE/add.jcl
  echo "//* MEMBER -------'                                                      " >> $WORKSPACE/add.jcl
  echo "/*                                                                       " >> $WORKSPACE/add.jcl
  echo "// IF MBRCOPY.RC < 8 THEN                                                " >> $WORKSPACE/add.jcl
  echo "//* --------------------------------------------------------------- *//  " >> $WORKSPACE/add.jcl
  echo "//* ADD ELEMENT TO CODE PIPELINE REPOSITORY                         *//  " >> $WORKSPACE/add.jcl
  echo "//* --------------------------------------------------------------- *//  " >> $WORKSPACE/add.jcl
  echo "//*                                   .---------- INSTANZ T=TEST/P=PROD  " >> $WORKSPACE/add.jcl
  echo "//*                                   !                                  " >> $WORKSPACE/add.jcl
  echo "//*                                   V                                  " >> $WORKSPACE/add.jcl
  echo "//MBRADD   EXEC PGM=WZZRCJOB,PARM='ISP${ISPW}/WZZECIJ'                   " >> $WORKSPACE/add.jcl
  echo "//STEPLIB  DD DISP=SHR,DSN=IZS.ISPW.S0T.SPWMLOAD                         " >> $WORKSPACE/add.jcl
  echo "//WZZOUT   DD SYSOUT=*                                                   " >> $WORKSPACE/add.jcl
  echo "//WORKIN   DD *                                                          " >> $WORKSPACE/add.jcl
  echo "\$DEFINE_TSI                                                             " >> $WORKSPACE/add.jcl
  echo "  STRMNAME=BOAS                                                          " >> $WORKSPACE/add.jcl
  echo "  APPLID=${SUBSYS}                                                       " >> $WORKSPACE/add.jcl
  echo "  SUBAPPL=${SUBSYS}                                                      " >> $WORKSPACE/add.jcl
  echo "  MTYPE=TONICZ                                                           " >> $WORKSPACE/add.jcl
  echo "  MNAME=$2                                                               " >> $WORKSPACE/add.jcl
  echo "  PROJNO=${ASSIGNMENT}                                                   " >> $WORKSPACE/add.jcl
  echo "  CLVL=${LEVEL}                                                          " >> $WORKSPACE/add.jcl
  echo "  SLVL=${LEVEL}                                                          " >> $WORKSPACE/add.jcl
  echo "/*                                                                       " >> $WORKSPACE/add.jcl
  echo "// ENDIF                                                                 " >> $WORKSPACE/add.jcl
  echo "//                                                                       " >> $WORKSPACE/add.jcl


  chmod u+x $WORKSPACE/upload.py

  $WORKSPACE/upload.py
  
  rm $WORKSPACE/upload.py
  rm $WORKSPACE/add.jcl

}

function createFull() {
  createDiffVorrelease "$1" "$2" "$3"
  cd $WORKSPACE/NEWTAG
  tar -czf ../${MANDANT}$2F.tgz ./$1
  tar -tvzf ../${MANDANT}$2F.tgz > $WORKSPACE/inhalt_tar.txt
  cd $WORKSPACE/DELTA
  mkdir "$1"
  rm ${MANDANT}$2D.txt || true
  touch ${MANDANT}$2D.txt
  tar -czf ../${MANDANT}$2D.tgz *
  rm -R *
  cd $WORKSPACE
  cp ${MANDANT}$2F.tgz /nfs/mtext/trans/${MANDANT}$2F.tgz
  uploadHost $WORKSPACE/${MANDANT}$2F.tgz ${MANDANT}$2F
  rm ${MANDANT}$2F.tgz
  cp ${MANDANT}$2D.tgz /nfs/mtext/trans/${MANDANT}$2D.tgz
  uploadHost $WORKSPACE/${MANDANT}$2D.tgz ${MANDANT}$2D
  rm ${MANDANT}$2D.tgz
  mailInfos "$1" "FULL" "$3"
}

function createDiffVorrelease() {
  touch $WORKSPACE/diff_tags_change.txt
  if [[ "${VORRELEASE}" != "R001.100" ]]; then
    cd $WORKSPACE
    svn diff --summarize --ignore-properties --username=${usr} --password=${pass} ./VORRELEASE/$1 https://itv-mtext-svn.en4920.de${REPOS}/tags/${RELEASE}_MText/$3 > diff_tags_change.txt
  fi
}

function createDelta() {
  createDiffVorrelease "$1" "$2" "$3"
  cd $WORKSPACE
  svn diff --summarize --ignore-properties --username=${usr} --password=${pass} ./OLD/$1 https://itv-mtext-svn.en4920.de${REPOS}/tags/${RELEASE}_MText/$3 > diff_change.txt
  cd $WORKSPACE/DELTA
  mkdir "$1"
  rm ${MANDANT}$2D.txt || true
  touch ${MANDANT}$2D.txt
  while read in; do
    AKTION="${in:0:1}"
    DATEI="${in:12}"
    if [[ -f "$WORKSPACE/NEW/$DATEI" ]]; then
      DATEIDIR="$(dirname "$DATEI")"
      DATEINAME="$(basename "$DATEI")"
      if [[ "${AKTION}" = "A" ]] || [[ ${AKTION} = "M" ]]; then
        #Datei wurde geändert und muss in die Delta-Datei
        mkdir -p "$WORKSPACE/DELTA/$DATEIDIR" && cp "$WORKSPACE/NEW/$DATEI" "$WORKSPACE/DELTA/$DATEIDIR"
      fi
    elif [[ "${AKTION}" = "D" ]]; then
      #Datei wurde gelöscht und muss in die Löschliste
      echo "${DATEI}" >> $WORKSPACE/DELTA/${MANDANT}$2D.txt
    fi
  done < ../diff_change.txt
  tar -czf ../${MANDANT}$2D.tgz *
  tar -tvzf ../${MANDANT}$2D.tgz > $WORKSPACE/inhalt_tar.txt
  rm -R *
  cd $WORKSPACE
  rm diff_change.txt || true
  cp ${MANDANT}$2D.tgz /nfs/mtext/trans/${MANDANT}$2D.tgz
  uploadHost $WORKSPACE/${MANDANT}$2D.tgz ${MANDANT}$2D
  rm ${MANDANT}$2D.tgz
  mailInfos "$1" "DELTA" "$3"
}

function mailInfos() {
  BETREFF="Bereitstellung ${MANDANT} - $1 - $2 - Release ${RELEASE}"
  echo "Subject: ${BETREFF}" > $WORKSPACE/email.txt
  if [[ -f "$WORKSPACE/diff_tags_change.txt" ]]; then
    echo "" >> $WORKSPACE/email.txt
    echo "Folgende DIFFs wurden beim Vergleich zwischen ${VORRELEASE} und ${RELEASE} fuer Mandant ${MANDANT} und das Projekt $1 in der Lieferung vom Typ $2 erkannt:"  >> $WORKSPACE/email.txt
    echo "" >> $WORKSPACE/email.txt
    cat $WORKSPACE/diff_tags_change.txt   >> $WORKSPACE/email.txt
    rm -R $WORKSPACE/diff_tags_change.txt
    echo ""   >> $WORKSPACE/email.txt
    echo ""   >> $WORKSPACE/email.txt
  fi
  if [[ -f "$WORKSPACE/inhalt_tar.txt" ]]; then
    echo "" >> $WORKSPACE/email.txt
    echo "Folgender Inhalt ist im TAR-Archiv fuer Mandant ${MANDANT} und das Projekt $1 in der Lieferung vom Typ $2 enthalten:"   >> $WORKSPACE/email.txt
    echo "" >> $WORKSPACE/email.txt
    cat $WORKSPACE/inhalt_tar.txt  >> $WORKSPACE/email.txt
    rm -R $WORKSPACE/inhalt_tar.txt
    echo ""   >> $WORKSPACE/email.txt
    echo ""   >> $WORKSPACE/email.txt
  fi
  cat $WORKSPACE/email.txt | mail -s "${BETREFF}" text-osp-lbs@f-i.de
  cp $WORKSPACE/email.txt /nfs/mtext/trans/_INFO_${MANDANT}-$1-$2-${RELEASE}-${VORRELEASE}.txt
  rm $WORKSPACE/email.txt
}

echo "Revision $REVISION"
echo "URL $REPOS"
echo "MANDANT $MANDANT"
echo "ART $ART"
echo "RELEASE $RELEASE"

REL="${RELEASE:0:4}"
STAGE=FKT

if   [ "$REL" = "R260" ]; then 
  linie=X 
  STAGE=JUR
elif [ "$REL" = "R261" ]; then 
  linie=Y
  STAGE=FKT
elif [ "$REL" = "R270" ]; then 
  linie=Z
  STAGE=JUR
elif [ "$REL" = "R251" ]; then 
  linie=W
  STAGE=JUR
else 
  linie=A
  STAGE=FKT
fi

ISPW=P

case $MANDANT in

  FI)
    if [ "$STAGE" = "FKT" ]; then 
      ASSIGNMENT=LOMS000066
	  LEVEL=FKTE
    else 
      ASSIGNMENT=LOMS000067
	  LEVEL=JURP
    fi
    ;;
  BY)
    if [ "$STAGE" = "FKT" ]; then 
      ASSIGNMENT=BYMT000055
	  LEVEL=FKTE
    else 
      ASSIGNMENT=BYMT000056
	  LEVEL=JURP
    fi
    ;;
  LH)
    if [ "$STAGE" = "FKT" ]; then 
      ASSIGNMENT=LHMT000022
	  LEVEL=FKTE
    else 
      ASSIGNMENT=LHMT000023
	  LEVEL=JURP
    fi
    ;;
  NW)
    if [ "$STAGE" = "FKT" ]; then 
      ASSIGNMENT=NWMT000073
	  LEVEL=FKTE
    else 
      ASSIGNMENT=NWMT000074
	  LEVEL=JURP
    fi
    ;;
  OS)
    if [ "$STAGE" = "FKT" ]; then 
      ASSIGNMENT=OSMT000047
	  LEVEL=FKTE
    else 
      ASSIGNMENT=OSMT000048
	  LEVEL=JURP
    fi
    ;;
  SA)
    if [ "$STAGE" = "FKT" ]; then 
      ASSIGNMENT=SAMT000031
	  LEVEL=FKTE
    else 
      ASSIGNMENT=SAMT000032
	  LEVEL=JURP
    fi
    ;;
  IT)
    if [ "$STAGE" = "FKT" ]; then 
      ASSIGNMENT=ITMT000031
	  LEVEL=FKTE
    else 
      ASSIGNMENT=ITMT000032
	  LEVEL=JURP
    fi
    ;;
  *)
    if [ "$STAGE" = "FKT" ]; then 
      ASSIGNMENT=LOMS000066
	  LEVEL=FKTE
    else 
      ASSIGNMENT=LOMS000067
	  LEVEL=JURP
    fi
    ;;
esac

if [ "$ART" = "Entwicklung" ]; then 
  umgebung=E
  server="https://${linie}A.fiv-mtext-do1.en4920.de"
fi
if [ "$ART" = "Abnahme" ]; then
  umgebung=A
  server="https://${linie}A.fiv-mtext-do0.en4920.de"
fi

echo "Linie = $linie"
echo "Umgebung = $umgebung"
echo "Server = $server"

if [[ "${ART}" = "Entwicklung" ]] || [[ "${ART}" = "Abnahme" ]]; then
  if [[ "${UMFANG}" == "FULL" ]]; then
    if [[ "${MANDANT}" == "FI" ]]; then
        createProject "Configuration" "Configuration" 
        createProject "Fonts" "Fonts" 
        createProject "LOMS_Framework" "LOMS_Framework" 
        createProject "LOMS_Basis" "LOMS_Basis"
        createProject "LOMS_PKA" "LOMS_PKA"
    elif [[ "${MANDANT}" == "IT" ]]; then
        createProject "LOMS_Autonom" "LOMS_Autonom" 
    else
        createProject "LOMS_Basis[${MANDANT}]" "LOMS_Basis%5b${MANDANT}%5d" 
        createProject "LOMS_Autonom[${MANDANT}]" "LOMS_Autonom%5b${MANDANT}%5d" 
    fi
  else
    if [[ "${MANDANT}" == "FI" ]]; then
        updateProject "Configuration" "Configuration"
        updateProject "Fonts" "Fonts"
        updateProject "LOMS_Framework" "LOMS_Framework"
        updateProject "LOMS_Basis" "LOMS_Basis"
        updateProject "LOMS_PKA" "LOMS_PKA"
    elif [[ "${MANDANT}" == "IT" ]]; then
        updateProject "LOMS_Autonom" "LOMS_Autonom"
    else
        updateProject "LOMS_Basis[${MANDANT}]" "LOMS_Basis%5b${MANDANT}%5d"
        updateProject "LOMS_Autonom[${MANDANT}]" "LOMS_Autonom%5b${MANDANT}%5d"
    fi
  fi

  if [[ "${ART}" = "Entwicklung" ]] && [[ "${linie}" = "W" ]] && [[ "${MANDANT}" == "FI" ]]; then
    if [[ "${UMFANG}" == "FULL" ]]; then
      createProject "LOMS_Basis[FI]" "LOMS_Basis%5bFI%5d"
    else
      updateProject "LOMS_Basis[FI]" "LOMS_Basis%5bFI%5d"
    fi
  fi
  echo "Start curl"
curl --show-error --silent \
     --header "Content-Type: application/json" \
     --request POST \
     --data ' {"mandant":"MAN", "institut": "INR"}' \
     --write-out "\nHTTP_STATUS=%{http_code}\n" \
     "$server/vMtextAdapter/sync"
fi

if [[ "${ART}" == "Bereitstellung" ]] && [[ ! -z "${RELEASE}" ]]; then
  mkdir -p $WORKSPACE/VORRELEASE
  svn list --username=${usr} --password=${pass} https://itv-mtext-svn.en4920.de${REPOS}/tags > $WORKSPACE/tags_listing.txt
  VORRELEASE="R001.100"
  
  while read in; do
    ZEILE="${in:0:8}"
    if [[ "${ZEILE}" < "${RELEASE}" ]] && [[ "${ZEILE}" > "${VORRELEASE}" ]]; then
      VORRELEASE="${ZEILE}"
    fi
  done < $WORKSPACE/tags_listing.txt

  if [[ "${VORRELEASE}" != "R001.100" ]]; then
    svn checkout --quiet --username=${usr} --password=${pass} https://itv-mtext-svn.en4920.de${REPOS}/tags/${VORRELEASE}_MText $WORKSPACE/VORRELEASE
  fi

  if [[ "${RELEASE:5:3}" != "100" ]]; then
    # Es handelt sich um eine DELTA-Lieferung!
    mkdir -p $WORKSPACE/DELTA
    HAUPTRELEASE="${RELEASE:0:4}.100"
    echo "Deltalieferung zwischen ${HAUPTRELEASE} und ${RELEASE}"
    svn checkout --quiet --username=${usr} --password=${pass} https://itv-mtext-svn.en4920.de${REPOS}/tags/${HAUPTRELEASE}_MText $WORKSPACE/OLD
    svn export --quiet --username=${usr} --password=${pass} https://itv-mtext-svn.en4920.de${REPOS}/tags/${RELEASE}_MText $WORKSPACE/NEW
    if [ -d "$WORKSPACE/NEW" ]; then
      mkdir -p $WORKSPACE/DELTA
      if [[ "${MANDANT}" == "FI" ]]; then
          SUBSYS="LOMS"
          createDelta "Configuration" "CONFI" "Configuration"
          createDelta "Fonts" "FONTS" "Fonts"
          createDelta "LOMS_Framework" "FRAME" "LOMS_Framework"
          createDelta "LOMS_Basis" "BASIS" "LOMS_Basis"
          createDelta "LOMS_PKA" "PKA" "LOMS_PKA"
      elif [[ "${MANDANT}" == "IT" ]]; then
          SUBSYS="ITMT"
          createDelta "LOMS_Autonom" "AUTON" "LOMS_Autonom"
      else
          SUBSYS="${MANDANT}MT"
          createDelta "LOMS_Basis[${MANDANT}]" "BASIS" "LOMS_Basis%5b${MANDANT}%5d"
          createDelta "LOMS_Autonom[${MANDANT}]" "AUTON" "LOMS_Autonom%5b${MANDANT}%5d"
      fi
      chmod u+w -R $WORKSPACE/OLD
      rm -R $WORKSPACE/OLD
      rm -R $WORKSPACE/NEW
      rm -R $WORKSPACE/DELTA
    fi
  else
    # Es handelt sich um eine VOLL-Lieferung!
    echo "Volllieferung zum ${RELEASE}"
    svn export --username=${usr} --password=${pass} https://itv-mtext-svn.en4920.de${REPOS}/tags/${RELEASE}_MText $WORKSPACE/NEWTAG
    if [ -d "$WORKSPACE/NEWTAG" ]; then
      mkdir -p $WORKSPACE/DELTA
      if [[ "${MANDANT}" == "FI" ]]; then
          SUBSYS="LOMS"
          createFull "Configuration" "CONFI" "Configuration"
          createFull "Fonts" "FONTS" "Fonts"
          createFull "LOMS_Framework" "FRAME" "LOMS_Framework"
          createFull "LOMS_Basis" "BASIS" "LOMS_Basis"
          createFull "LOMS_PKA" "PKA" "LOMS_PKA"
      elif [[ "${MANDANT}" == "IT" ]]; then
          SUBSYS="ITMT"
          createFull "LOMS_Autonom" "AUTON" "LOMS_Autonom"
      else
          SUBSYS="${MANDANT}MT"
          createFull "LOMS_Basis[${MANDANT}]" "BASIS" "LOMS_Basis%5b${MANDANT}%5d"
          createFull "LOMS_Autonom[${MANDANT}]" "AUTON" "LOMS_Autonom%5b${MANDANT}%5d"
      fi
      rm -R $WORKSPACE/NEWTAG
      rm -R $WORKSPACE/DELTA
    fi
  fi
  rm -R $WORKSPACE/tags_listing.txt
  chmod u+w -R $WORKSPACE/VORRELEASE
  rm -R $WORKSPACE/VORRELEASE
fi  
