from geant4_pybind import *
import argparse
import copy
import csv
import configparser
import json
import os
import datetime
import calendar
import sys
import random
import math
from pyEcoMug import EcoMug
from util_math_functions import *
from scene_config import load_scene


class ActionInitialization(G4VUserActionInitialization):
    
    def __init__(self, detectorConstruction):
        super().__init__()
        self.fDetector = detectorConstruction
        
    def BuildForMaster(self):
        runAction = RunAction()
        self.SetUserAction(runAction)
        
    def Build(self):
        fileman = FileManager.GetFileManager()
        ptree = fileman.GetPropTree()
        inputMethod = int(ptree.get("input","method"))
        self.SetUserAction(PrimaryGeneratorAction())
        runAction = RunAction()
        self.SetUserAction(runAction)


class DetectorConstruction(G4VUserDetectorConstruction):
    
    def __init__(self, scene=None, useCubeFile=False, cubeFileName="cubeInfo.txt"):
        super().__init__()
        self.detLog = None
        self.scene = scene
        self.useCubeFile = useCubeFile
        self.cubeFileName = cubeFileName # The corresponding file defines the properties of the cube in the scene
        if scene:
            det = scene.get("detector", {})
            self.detSide = float(det.get("side", 1.0))
            self.topZ = float(det.get("topZ", 0.8))
            self.bottomZ = float(det.get("bottomZ", 0.0))
        else:
            self.detSide = 1.0
            self.topZ = 0.8
            self.bottomZ = 0.0
        self.target_log_vols = []
        self.traversal_state = TraversalState()
        
    def Construct(self):
        man = G4NistManager.Instance()
        matAir = man.FindOrBuildMaterial("G4_AIR")

        # Materials for concrete
        matH  = man.FindOrBuildMaterial("G4_H")
        matO  = man.FindOrBuildMaterial("G4_O")
        matNA = man.FindOrBuildMaterial("G4_Na")
        matAl = man.FindOrBuildMaterial("G4_Al")
        matSi = man.FindOrBuildMaterial("G4_Si")
        matCa = man.FindOrBuildMaterial("G4_Ca")
        matFe = man.FindOrBuildMaterial("G4_Fe") 

        # Make concrete
        densityConcrete = 2.3*g/cm3
        ncompsConcrete = 7
        mat_concrete = G4Material("concrete", densityConcrete, ncompsConcrete)
        mat_concrete.AddMaterial(matH, 0.168038)
        mat_concrete.AddMaterial(matO, 0.563183)
        mat_concrete.AddMaterial(matNA, 0.021365)
        mat_concrete.AddMaterial(matAl, 0.021343)
        mat_concrete.AddMaterial(matSi, 0.203231)
        mat_concrete.AddMaterial(matCa, 0.018595)
        mat_concrete.AddMaterial(matFe, 0.004246)
    
        # steel for frontdoor
        matC = man.FindOrBuildMaterial("G4_C")
  
        densitySteel = 7.82*g/cm3
        ncompsSteel = 2
        mat_steel = G4Material("steel", densitySteel, ncompsSteel)
        mat_steel.AddMaterial(matC, 0.022831)
        mat_steel.AddMaterial(matFe, 0.977169)
  
        # steel concrete for walls 
        frac_steel = 300.0 /(densitySteel/(g/cm3)*1e3)
        frac_concrete = 1.0 - frac_steel
        density_wall = frac_concrete*densityConcrete + frac_steel*densitySteel
        ncompsWall = 2
        matWall = G4Material("steelconcrete",density_wall, ncompsWall)
        matWall.AddMaterial(mat_concrete, frac_concrete)
        matWall.AddMaterial(mat_steel, frac_steel)
  
        #------------------------------- WORLD VOLUME, filled with air------------------------------------#
        checkOverlaps = True
        placement = G4ThreeVector(0,0,0)
  
        axisX = G4ThreeVector(1.0,0,0)
        axisY = G4ThreeVector(0,1.0,0)
        axisZ = G4ThreeVector(0,0,1.0)
    
        solidWorld = G4Sphere("World", 0.0*cm, 22.0*m,
                                                 0.0*deg, 360.0*deg,
                                                 0.0*deg, 180.0*deg)
        logicWorld = G4LogicalVolume(solidWorld, matAir, "World")
        physWorld = G4PVPlacement(None, 
                          G4ThreeVector(),
                          logicWorld,
  			  "World ",
                           None,
                           False,
                           0)
    
        #-------------------------------------BUNKER---------------------------------------------------#
        #--------------------bunker measures-------------------------------#
        length = 30.78 *m
        width  = 15.0  *m
  
        pash1 = 1.102 *m
        pash4 = 1.615 *m
  
        pRMin = 9.71 *m
        pRMax = 10.81*m 
    
        sidewidth  = (12.68/2.0)*m
        sideheight = 5.072*m
    
  
    
        #------------------parts of bunker---------------------------------#
        #------roof------#
        heightRoof = pash1/2  #constructors take half
        widthRoof = width/2
        lengthRoof = length/2
        zPosRoof = 3.97*m + heightRoof
  
        concSolid = G4Box("concSolid",widthRoof,lengthRoof,heightRoof)
        concLog = G4LogicalVolume(concSolid, matWall, "roofLog")
        placementconc = G4ThreeVector(0.0, 0.0, zPosRoof)
  
        concPhysical = G4PVPlacement(None,                       #no rotation
                                                       placementconc,            #at
                                                       concLog,                  #its logical volume
                                                       "Conc",                   #its name
                                                       logicWorld,               #its mother  volume
                                                       False,                    #no boolean operation
                                                       0,                        #copy number
                                                       checkOverlaps)
  
        #------sides-----#
        v0=G4TwoVector(0*m, 0*m)
        v1=G4TwoVector(0*m, 0*m+sideheight)
        v2=G4TwoVector(sidewidth, 0*m)
        v2_2=G4TwoVector(0*m-sidewidth, 0*m)
        vertices = G4TwoVectorVector([v0,v1,v2,v2,v0,v1,v2,v2])
        vertices_2 = G4TwoVectorVector([v0,v1,v2_2,v2_2,v0,v1,v2_2,v2_2])
        sideSolid = G4GenericTrap("bunker side", length/2.0, vertices)
        sideSolid_2 = G4GenericTrap("bunker side", length/2.0, vertices_2)
        
        sideLog = G4LogicalVolume(sideSolid, matWall, "wallLog")
        sideLog_2 = G4LogicalVolume(sideSolid_2, matWall, "wallLog")

        rotA = G4RotationMatrix()
        rotA.rotate(-90*deg, axisX)
        
        sidePhysical1 = G4PVPlacement(rotA,                           
                                      G4ThreeVector(widthRoof,0.0,0.0),   
                                      sideLog,                         
                                      "side1",                          
                                      logicWorld,                       
                                      False,                           
                                      0,                               
                                      checkOverlaps);
        
        sidePhysical2 = G4PVPlacement(rotA,                          
                                      G4ThreeVector(-widthRoof,0.0,0.0),  #at
                                      sideLog_2,                        #its logical volume
                                      "side2",                          #its name
                                      logicWorld,                       #its mother  volume
                                      False,                            #no boolean operation
                                      0,                                #copy number
                                      checkOverlaps)
        
        #-----backwall------#
        backWallthickness = pash1/2.0
        backWallheight = (3.97/2.0)*m
        backSolid = G4Box("concSolid",widthRoof, backWallthickness,backWallheight)                                                  
        backLog = G4LogicalVolume(backSolid, matWall, "backLog")
        placementBackWall=G4ThreeVector(0,-lengthRoof+backWallthickness,backWallheight)
        
        backPhysical = G4PVPlacement(None,                       #no rotation
                                     placementBackWall,        #at
                                     backLog,                  #its logical volume
                                     "back",                   #its name
                                     logicWorld,               #its mother  volume
                                     False,                    #no boolean operation
                                     0,                        #copy number
                                     checkOverlaps);
        
        #-----front door-----#
        frontLog = G4LogicalVolume(backSolid, mat_steel, "frontLog");   
        dooroffset = 3.0*m
        placementFrontDoor=G4ThreeVector(0,+lengthRoof-dooroffset-backWallthickness,backWallheight)
        
        frontPhysical = G4PVPlacement(None,                       #no rotation
                                      placementFrontDoor,        #at
                                      frontLog,                  #its logical volume
                                      "front",                   #its name
                                      logicWorld,                #its mother  volume
                                      False,                     #no boolean operation
                                      0,                         #copy number
                                      checkOverlaps)
        
        
        
        #----------------------------DETECTOR------------------------------#
        detMaterial = man.FindOrBuildMaterial("G4_PLASTIC_SC_VINYLTOLUENE")
        detSide   = self.detSide*m       
        detHeight = 2.5*mm      
        detSolid = G4Box("detSolid",detSide, detSide,detHeight)
        self.detLog = G4LogicalVolume(detSolid, detMaterial, "detLog")

        # Detector placements
        detLowerOut = G4PVPlacement(None,
                                    G4ThreeVector(0.0,0.0,self.bottomZ*m), 
                                    self.detLog,
                                         "Lower Detector Out",
                                    logicWorld,
                                    False,
                                    3,
                                    checkOverlaps)
        detLowerIn = G4PVPlacement(None,
                                    G4ThreeVector(0.0,0.0,self.bottomZ*m+2*detHeight),
                                    self.detLog,
                                        "Lower Detector In",
                                    logicWorld,
                                    False,
                                    2,
                                    checkOverlaps)
        detUpperOut = G4PVPlacement(None,
                                    G4ThreeVector(0.0,0.0,self.topZ*m-2*detHeight),
                                    self.detLog,
                                         "Upper Detector Out",
                                    logicWorld,
                                    False,
                                    1,
                                    checkOverlaps)
        detUpperIn = G4PVPlacement(None,
                                   G4ThreeVector(0.0,0.0,self.topZ*m),
                                    self.detLog,
                                        "Upper Detector In",
                                    logicWorld,
                                    False,
                                    0,
                                    checkOverlaps)
        
        #-------------------------Cubes for testing--------------------------#
        if self.scene and self.scene.get("objects"):
            count = 0
            for obj in self.scene["objects"]:
                centerX = float(obj["pX"])*m
                centerY = float(obj["pY"])*m
                centerZ = float(obj["pZ"])*m
                matName = obj["mat"] if obj["mat"].startswith("G4_") else "G4_"+obj["mat"]
                mat = man.FindOrBuildMaterial(matName)
                shape = obj.get("shape", "box")
                if shape == "box":
                    half = float(obj["halfSide"])*m
                    solid = G4Box("obj"+str(count), half, half, half)
                elif shape == "cylinder":
                    solid = G4Tubs("obj"+str(count), 0, float(obj["radius"])*m,
                                   float(obj["halfHeight"])*m, 0, 360.0*deg)
                else:
                    raise ValueError("unsupported object shape: "+str(shape))
                logVol = G4LogicalVolume(solid, mat, "objLog"+str(count))
                G4PVPlacement(None,
                              G4ThreeVector(centerX, centerY, centerZ),
                              logVol,
                              "objPhys"+str(count),
                              logicWorld,
                              False,
                              0,
                              checkOverlaps)
                self.target_log_vols.append(logVol)
                count += 1
        elif self.useCubeFile:
            with open(self.cubeFileName, "r") as cubeInfo:
                reader = csv.reader(cubeInfo)
                next(reader) # Skip the first line, it's just column titles
                count = 0
                for row in reader:
                    centerX = float(row[0])*m
                    centerY = float(row[1])*m
                    centerZ = float(row[2])*m
                    sideLengthHalf = float(row[3])*m
                    mat = man.FindOrBuildMaterial("G4_"+row[4])
                    cubeSolid = G4Box("cube"+str(count), sideLengthHalf, sideLengthHalf, sideLengthHalf)
                    cubeLog = G4LogicalVolume(cubeSolid, mat, "cubeLog"+str(count))
                    cubePhysical = G4PVPlacement(None,
                                                 G4ThreeVector(centerX, centerY, centerZ),
                                                 cubeLog,
                                                 "cubePhys"+str(count),
                                                 logicWorld,
                                                 False,
                                                 0,
                                                 checkOverlaps)
                    count += 1
        else:
            matPu = man.FindOrBuildMaterial("G4_Pu")
            matPb = man.FindOrBuildMaterial("G4_Fe")
            cubeX = 0.05*m
            cubeY = cubeX
            cubeZ = cubeX
            
            cubeSolid = G4Box("cubeSolid",cubeX, cubeY,cubeZ)
            cubeLogPb = G4LogicalVolume(cubeSolid, matPb, "cubeLogFe")
            cubeLogPu = G4LogicalVolume(cubeSolid, matPu, "cubeLogPu")
            cylSolid = G4Tubs("cylSolid", 0, 0.05*m, 0.05*m, 0, 360.0*deg)
            cylLogPb = G4LogicalVolume(cylSolid, matPb, "cylLogFe")
            cylLogPu = G4LogicalVolume(cylSolid, matPu, "cylLogPu")
            
            cubePhysicalPb = G4PVPlacement(None,                          #no rotation
        G4ThreeVector(0.3*m, 0.3*m, 0.4*m),
        cubeLogFe,                    #its logical volume
        "cubePhysFe",                     #its name
        logicWorld,                    #its mother  volume
        False,                      #no boolean operation
        0,                          #copy number
        checkOverlaps)              #overlaps checking
        
            cubePhysicalPu = G4PVPlacement(None,                          #no rotation
        G4ThreeVector(-0.3*m, -0.3*m, 0.4*m), # bad at detecting "far" from source
        cubeLogPu,                    #its logical volume
        "cubePhysPu",                     #its name
        logicWorld,                    #its mother  volume
        False,                      #no boolean operation
        0,                          #copy number
        checkOverlaps)              #overlaps checking

            cylPhysicalPb = G4PVPlacement(None,                          #no rotation
        G4ThreeVector(0.3*m, -0.3*m, 0.4*m),
        cylLogFe,                    #its logical volume
        "cylPhysFe",                     #its name
        logicWorld,                    #its mother  volume
        False,                      #no boolean operation
        0,                          #copy number
        checkOverlaps)              #overlaps checking

            cylPhysicalPu = G4PVPlacement(None,                          #no rotation
        G4ThreeVector(-0.3*m, 0.3*m, 0.4*m),
        cylLogPu,                    #its logical volume
        "cylPhysPu",                     #its name
        logicWorld,                    #its mother  volume
        False,                      #no boolean operation
        0,                          #copy number
        checkOverlaps)              #overlaps checking
            
        return physWorld

    
    def ConstructSDandField(self):
        run = self.scene.get("run", {}) if self.scene else {}
        gate_on_traversal = run.get("gatePoCAOnTargetTraversal", False)
        muonSensDet = MuonSensitiveDetector("MuonSensitiveDetector",
                                            self.topZ*m, self.bottomZ*m, 0, False,
                                            self.traversal_state, gate_on_traversal)
        if self.detLog != None:
            self.detLog.SetSensitiveDetector(muonSensDet)
        if self.target_log_vols:
            targetSensDet = TargetTraversalSD("TargetTraversalSD", self.traversal_state)
            for logVol in self.target_log_vols:
                logVol.SetSensitiveDetector(targetSensDet)
        
            
class FileManager:
    
    fileManInstance = None
    fptree = None
    resolved_scene = None
    
    def __init__(self):
        FileManager.fileManInstance = None
        FileManager.fptree = None
        FileManager.resolved_scene = None

    def GetFileManager():
        if FileManager.fileManInstance is None:
            FileManager.fileManInstance = FileManager()
            FileManager.fptree = configparser.ConfigParser()
        return FileManager.fileManInstance
        
    def ReadIniFile(self,filename):
        FileManager.fptree.read(filename)

    def LoadFromScene(self, scene):
        FileManager.fptree = configparser.ConfigParser()
        FileManager.resolved_scene = copy.deepcopy(scene)
        run = scene.get("run", {})
        source = scene.get("source", {})
        output = scene.get("output", {})
        geom = source.get("geometry", "halfSphere")
        geom_num = 2 if geom == "halfSphere" else 1
        FileManager.fptree.add_section("input")
        FileManager.fptree.set("input", "method", str(run.get("method", 2)))
        FileManager.fptree.add_section("ecomug")
        FileManager.fptree.set("ecomug", "geometry", str(geom_num))
        FileManager.fptree.set("ecomug", "centerX", str(source["centerX"]))
        FileManager.fptree.set("ecomug", "centerY", str(source["centerY"]))
        FileManager.fptree.set("ecomug", "centerZ", str(source["centerZ"]))
        FileManager.fptree.add_section("halfSphere")
        FileManager.fptree.set("halfSphere", "radius", str(source.get("radius", 0.06)))
        FileManager.fptree.add_section("sky")
        FileManager.fptree.set("sky", "sizeX", str(source.get("skySizeX", 1)))
        FileManager.fptree.set("sky", "sizeY", str(source.get("skySizeY", 1)))
        FileManager.fptree.add_section("output")
        FileManager.fptree.set("output", "pathname", output["pathname"])
        FileManager.fptree.set("output", "foldername", output["foldername"])

    def GetResolvedScene(self):
        return FileManager.resolved_scene

    def WriteResolvedScene(self, filename="scene.resolved.json"):
        scene = copy.deepcopy(FileManager.resolved_scene)
        path = FileManager.fptree.get("output", "pathname")
        name = FileManager.fptree.get("output", "foldername")
        pathname = path + name
        with open(pathname + "/" + filename, "w") as out:
            json.dump(scene, out, indent=2)
            out.write("\n")
        
    def CreateResultsDir(self):
        name = FileManager.fptree.get("output","foldername")
        path = FileManager.fptree.get("output","pathname")
        pathname = path+name
        # slightly different
        try:
            os.mkdir(pathname)
            print("results are stored at "+pathname)
        except:
            print("failed to create results directory, maybe it already exists?")
            
    def WriteIniFile(self,filename):
        method = int(FileManager.fptree.get("input","method"))
        name = FileManager.fptree.get("output","foldername")
        path = FileManager.fptree.get("output","pathname")
        pathname = path+name
        with open(pathname+"/"+filename, "w") as config_file:
            FileManager.fptree.write(config_file)
            
    
    def GetPropTree(self):
        return FileManager.fptree
    
    def AddValuePropTree(self, section, option, val):
        if not FileManager.fptree.has_section(section):
            FileManager.fptree.add_section(section)
        FileManager.fptree.set(section, option, val)


class PrimaryGeneratorAction(G4VUserPrimaryGeneratorAction):
    
    def __init__(self):
        super().__init__()
        self.fparticleTable = G4ParticleTable.GetParticleTable()
        self.fparticleGun = G4ParticleGun()
        self.fmuonGen = EcoMug()
        fileman = FileManager.GetFileManager()
        ptree = fileman.GetPropTree()

        geometry = float(ptree.get("ecomug","geometry"))
        centerX = float(ptree.get("ecomug","centerX"))
        centerY = float(ptree.get("ecomug","centerY"))
        centerZ = float(ptree.get("ecomug","centerZ"))

        skySizeX = 0.0
        skySizeY = 0.0
        radius = 0.0

        if (geometry == 1): # plane surface
            self.fmuonGen.SetUseSky()
            skySizeX = float(ptree.get("sky","sizeX"))
            skySizeY = float(ptree.get("sky","sizeY"))
            self.fmuonGen.SetSkySize([skySizeX, skySizeY]) # x and y size of plane
            self.fmuonGen.SetSkyCenterPosition([centerX,centerY,centerZ])
        elif geometry == 2: # half-sphere
            self.fmuonGen.SetUseHSphere()
            radius = float(ptree.get("halfSphere","radius"))
            self.fmuonGen.SetHSphereRadius(radius)
            self.fmuonGen.SetHSphereCenterPosition([centerX,centerY,centerZ])
        else:
            print("---Problem with EcoMugGeometry!---")

        particleName = ""
        self.fparticleAntiMu = self.fparticleTable.FindParticle("mu-")
        self.fparticleMu = self.fparticleTable.FindParticle("mu+")

    def GeneratePrimaries(self, anEvent):
        particle = None
        self.fmuonGen.Generate()

        muonPos = self.fmuonGen.GetGenerationPosition()
        muon_ptot = self.fmuonGen.GetGenerationMomentum()
        muon_theta = self.fmuonGen.GetGenerationTheta()
        muon_phi = self.fmuonGen.GetGenerationPhi()
        muon_charge = self.fmuonGen.GetCharge()
  
        if(muon_charge > 0):
             particle = self.fparticleMu
        else:
            particle = self.fparticleAntiMu
        self.fparticleGun.SetParticleDefinition(particle)
        self.fparticleGun.SetParticlePosition(G4ThreeVector(muonPos[0]*m,muonPos[1]*m, muonPos[2]*m))
        self.fparticleGun.SetParticleMomentum(G4ThreeVector(
        muon_ptot*math.sin(muon_theta)*math.cos(muon_phi)*GeV,              #from spherical to cartesian coodinates
            muon_ptot*math.sin(muon_theta)*math.sin(muon_phi)*GeV,
            muon_ptot*math.cos(muon_theta)*GeV
        ))
        self.fparticleGun.GeneratePrimaryVertex(anEvent)


class RunAction(G4UserRunAction):
    
    def BeginOfRunAction(self,aRun):
        G4RunManager.GetRunManager().SetRandomNumberStore(False)
        fileman = FileManager.GetFileManager()
        ptree = fileman.GetPropTree()

        name = ptree.get("output","foldername")
        path = ptree.get("output","pathname")
        pathname = path+name

        # fix later
        eventsInRun = aRun.GetNumberOfEventToBeProcessed()
        fileman.AddValuePropTree("input","nparticles", str(eventsInRun))

        man = G4AnalysisManager.Instance()

        # Set up file to output results
        datetimeNow = datetime.datetime.now()
        formatted = datetime.datetime.strftime(datetimeNow, '%a%b%d%H%M')
        filename = pathname+"/results"+formatted+".csv"
        man.OpenFile(filename)
        man.SetVerboseLevel(1)
        man.CreateNtuple("Hits","hits")
        
        man.CreateNtupleIColumn("detectorNo") # Which detector it hit (actual detector or inside the block)
        man.CreateNtupleDColumn("fX") # PoCA x-coordinate
        man.CreateNtupleDColumn("fY") # y-coordinate
        man.CreateNtupleDColumn("fZ") # z-coordinate
        man.CreateNtupleDColumn("theta") # Scattering angle
        man.FinishNtuple(0)
        
    def EndOfRunAction(self,run):
        nofEvents = run.GetNumberOfEvent()
        if (nofEvents == 0):
            return
        detConstruction = G4RunManager.GetRunManager().GetUserDetectorConstruction()
        man = G4AnalysisManager.Instance()        
        man.Write()
        man.CloseFile()
        print("\n-----End of Run-----")
        resolved = FileManager.GetFileManager().GetResolvedScene()
        if resolved and resolved.get("run", {}).get("reportTargetTraversal", True):
            state = detConstruction.traversal_state
            n_plate = len(state.plate_crossing_events)
            n_target = len(state.traversed_events)
            pct = (100.0 * n_target / n_plate) if n_plate else 0.0
            print(f"Target traversal: {n_target}/{n_plate} ({pct:.2f}%)")
            if n_target == 0:
                print("WARNING: zero target traversals — poor overlap/voxel metrics may "
                      "reflect unreachable geometry (misaligned source, target outside "
                      "illuminated cone, etc.), not necessarily broken PoCA.")
        
        
class TraversalState:
    def __init__(self):
        self.plate_crossing_events = set()
        self.traversed_events = set()


class TargetTraversalSD(G4VSensitiveDetector):
    def __init__(self, SDname, traversal_state):
        super().__init__(SDname)
        self.traversal_state = traversal_state

    def ProcessHits(self, step, ROhist):
        pName = step.GetTrack().GetDefinition().GetParticleName()
        if pName[0:2] == "mu":
            evt = G4RunManager.GetRunManager().GetCurrentEvent().GetEventID()
            self.traversal_state.traversed_events.add(evt)
        return True


class MuonSensitiveDetector(G4VSensitiveDetector):
    def __init__(self, SDname, topZ, bottomZ, detectorNo, noise=False,
                 traversal_state=None, gate_on_traversal=False):
        super().__init__(SDname)
        self.eventIDtoFirstHitInfo = dict() # Store position+motion vector to calculate PoCA
        self.height = topZ - bottomZ
        self.detectorNo = detectorNo
        self.topZ = topZ
        self.bottomZ = bottomZ
        self.addNoise = noise
        self.traversal_state = traversal_state
        self.gate_on_traversal = gate_on_traversal

    def ProcessHits(self,step, ROhist):
        pName = step.GetTrack().GetDefinition().GetParticleName()
        if (pName[0:2] == "mu"):
            preCopyNo = step.GetPreStepPoint().GetTouchable().GetVolume().GetCopyNo()
            postCopyNo = step.GetPostStepPoint().GetTouchable().GetVolume().GetCopyNo()
            evt = G4RunManager.GetRunManager().GetCurrentEvent().GetEventID()
            # Going through top layer (entering detector)
            if preCopyNo == 0 and postCopyNo == 1:
                posPreVec = step.GetPreStepPoint().GetPosition() 
                posPreTuple = (posPreVec.getX(), posPreVec.getY(), posPreVec.getZ())
                dirVec = step.GetTrack().GetMomentumDirection() 
                dirTuple = (dirVec.getX(), dirVec.getY(), dirVec.getZ())
                self.eventIDtoFirstHitInfo[evt] = DetectorHitTrajectory(posPreTuple, dirTuple)
            # Exiting detector (bottom layer)
            elif preCopyNo == 2 and postCopyNo == 3:
                if self.traversal_state is not None:
                    self.traversal_state.plate_crossing_events.add(evt)
                # Find the same muon's information when entering the detector
                if evt in self.eventIDtoFirstHitInfo.keys():
                    posPostVec = step.GetPostStepPoint().GetPosition()
                    posPostTuple = (posPostVec.getX(), posPostVec.getY(), posPostVec.getZ())
                    dirVec = step.GetTrack().GetMomentumDirection()
                    dirTuple = (dirVec.getX(), dirVec.getY(), dirVec.getZ())
                    firstHitPosPre = self.eventIDtoFirstHitInfo[evt].posPre # Position of muon when entering detector
                    firstHitDir = self.eventIDtoFirstHitInfo[evt].direction # Direction of muon when entering detector
                    # Get point of closest approach
                    closestApproach = POCA(firstHitPosPre, firstHitDir, posPostTuple, dirTuple)
                    if self.addNoise:
                        closestApproach = (closestApproach[0]+random.gauss(0.0,1.0)/10, closestApproach[1]+random.gauss(0.0,1.0)/10, closestApproach[2]+random.gauss(0.0,1.0)/10)        
                    approxFirstTrajectory = subtract(closestApproach, firstHitPosPre)
                    approxSecondTrajectory = subtract(posPostTuple, closestApproach)
                    scatteringAngle = angleBetween(approxFirstTrajectory, approxSecondTrajectory)
                    # Remove outliers near top/bottom plates; keep PoCA z inside symmetric band
                    margin = self.height / 10
                    if (1.5 < scatteringAngle < 30
                            and self.bottomZ + margin < closestApproach[2] < self.topZ - margin):
                        if (self.gate_on_traversal
                                and evt not in self.traversal_state.traversed_events):
                            return True
                        aMan = G4AnalysisManager.Instance()
                        aMan.FillNtupleIColumn(0, self.detectorNo)
                        aMan.FillNtupleDColumn(1, closestApproach[0])
                        aMan.FillNtupleDColumn(2, closestApproach[1])
                        aMan.FillNtupleDColumn(3, closestApproach[2])
                        aMan.FillNtupleDColumn(4, scatteringAngle)
                        aMan.AddNtupleRow(0)                  
                    
        return True          

    
class DetectorHitTrajectory:
    
    def __init__(self, posPre, dirVec):
        self.posPre = posPre
        self.direction = dirVec

        
def main():
    parser = argparse.ArgumentParser(description="Muon bunker Geant4 simulation")
    parser.add_argument("--config", default="scene.json",
                        help="Path to scene.json (default: scene.json)")
    parser.add_argument("mac", nargs="?", default="simpleRun.mac",
                        help="Geant4 macro file (default: simpleRun.mac)")
    args = parser.parse_args()

    start = datetime.datetime.now()
    # Can test with a set seed
    random.seed(1234)

    fileman = FileManager.GetFileManager()
    scene = load_scene(args.config)
    fileman.LoadFromScene(scene)
    fileman.CreateResultsDir()

    runManager = G4RunManagerFactory.CreateRunManager(G4RunManagerType.Default)

    macFileName = args.mac
        
    det = DetectorConstruction(scene=scene)
    runManager.SetUserInitialization(det)

    physicsList = QBBC()
    physicsList.SetVerboseLevel(1)
    runManager.SetUserInitialization(physicsList)

    runManager.SetUserInitialization(ActionInitialization(det))

    visManager = G4VisExecutive()
    visManager.Initialize()

    UImanager = G4UImanager.GetUIpointer()
    
    command = "/control/execute "
    UImanager.ApplyCommand(command+macFileName)
        
    stop = datetime.datetime.now()
    duration = (stop - start).seconds//60

    fileman.AddValuePropTree("output","duration", str(duration))
    fileman.AddValuePropTree("input","seed", "1234")
    fileman.WriteIniFile("parameters.ini")
    resolved = fileman.GetResolvedScene()
    if resolved is not None:
        run_out = resolved.setdefault("run", {})
        run_out["duration_minutes"] = duration
        run_out["seed"] = 1234
        run_out["nparticles"] = int(
            fileman.GetPropTree().get("input", "nparticles", fallback="0"))
        state = det.traversal_state
        n_plate = len(state.plate_crossing_events)
        n_target = len(state.traversed_events)
        run_out["plate_crossings"] = n_plate
        run_out["target_traversals"] = n_target
        run_out["traversal_fraction"] = (n_target / n_plate) if n_plate else 0.0
        fileman.WriteResolvedScene()


if __name__ == '__main__':
    main()
