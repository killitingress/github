//LIT9028A JOB (IE-00-TSO0-0000),'TONIC-SVN-UPLOAD',
//         MSGCLASS=H,CLASS=L,REGION=256M,NOTIFY=&SYSUID
//*-------------------------------------------------------------------+
//* =============================================================== *//
//* IMPORT UND REGISTRIERUNG EINES TONIC-ELEMENTS IN CODE PIPELINE  *//
//* =============================================================== *//
//*
//* --------------------------------------------------------------- *//
//* DIESER JOB BESTEHT AUS 2 STEPS.                                 *//
//*                                                                 *//
//*   NR. STEPNAME   PROGRAMM   FUNKTION                            *//
//*   -----------------------------------------------------------   *//
//*   1   MBRCOPY    IEBCOPY    KOPIEREN DES PHYSISCHEN MEMBERS     *//
//*                             IN DIE EMPFANGSDATEI VON CP         *//
//*   2   MBRADD     WZZRCJOB   REGISTRIEREN DER METADATEN ZUM      *//
//*                             NEUEN ELEMENT IM ZIEL-LEVEL         *//
//* --------------------------------------------------------------- *//
//*
//* --------------------------------------------------------------- *//
//* COPY MEMBER INTO CODE PIPELINE PDS                              *//
//* --------------------------------------------------------------- *//
//MBRCOPY  EXEC PGM=IEBCOPY
//SYSPRINT DD SYSOUT=*
//* QUELLDATEI ------------.
//*                        !
//*                        V
//COPYIN   DD DISP=SHR,DSN=IEA.LOMS.TONICZ
//* ZIELDATEI  ------------.       .------------- INSTANZ T=TEST/P=PROD
//*                        !       ! .----------- STREAM (BOAS)
//*                        !       ! !    .------ LEVEL  (FKTE/JURP)
//*                        !       ! !    !    .- TYPE   (TONICZ)
//*                        !       ! !    !    !
//*                        V       V V    V    V
//COPYOUT  DD DISP=SHR,DSN=IEA.ISPW@@ISPW@@.BOAS.@@LEVEL@@.TONICZ
//SYSIN    DD *
  COPYMOD OUTDD=COPYOUT,INDD=COPYIN,LIST=YES
  SELECT MEMBER=((@@MEMBER@@,,R))
/*
//*               !
//* MEMBER -------'
/*
// IF MBRCOPY.RC < 8 THEN
//* --------------------------------------------------------------- *//
//* ADD ELEMENT TO CODE PIPELINE REPOSITORY                         *//
//* --------------------------------------------------------------- *//
//*                                   .---------- INSTANZ T=TEST/P=PROD
//*                                   !
//*                                   V
//MBRADD   EXEC PGM=WZZRCJOB,PARM='ISP@@ISPW@@/WZZECIJ'
//STEPLIB  DD DISP=SHR,DSN=IZS.ISPW.S0T.SPWMLOAD
//WZZOUT   DD SYSOUT=*
//WORKIN   DD *
$DEFINE_TSI
  STRMNAME=BOAS
  APPLID=@@SUBSYS@@
  SUBAPPL=@@SUBSYS@@
  MTYPE=TONICZ
  MNAME=@@MEMBER@@
  PROJNO=@@ASSIGNMENT@@
  CLVL=@@LEVEL@@
  SLVL=@@LEVEL@@
/*
// ENDIF
//
