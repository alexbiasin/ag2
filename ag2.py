# Autor: Alejandro Biasin, 2020
# AG2 es un upgrade de AG1. Nuevos features:
#  - Mas object-oriented
#  - LOAD y SAVE game state

from __future__ import division
import pygame_textinput
# https://github.com/Nearoo/pygame-text-input
# otra opcion https://stackoverflow.com/questions/46390231/how-to-create-a-text-input-box-with-pygame
import pygame
from pygame.locals import *
from time import sleep
import random
from random import randrange
import math
import textwrap
import unicodedata
import os # para posicionar la ventana
from enum import Enum
import json # para guardar y cargar estado
import bz2
import pickle # grabar objetos en archivos
import _pickle as cPickle

# Opening JSON file 
#import json 
#with open('bosque.json') as json_file: 
#    data = json.load(json_file)

class Dir(str, Enum):
    none = -1
    E = 2
    SE = 20
    S = 0
    SW = 10
    W = 1
    NW = 30
    N = 3
    NE = 40
    

class Player(pygame.sprite.Sprite):
    def __init__(self, game):
        super(Player, self).__init__()

        self.game = game # Obtengo el objeto Game por parametro
        self.images = [] # sera una nested list        
        self.loadImages() # load images into array
        
        self.index = 0
        self.scale = 1
        self.move_step_max = 5 # tope fijo del step que luego varia por dt
        self.move_step = 76 # variable mediante DeltaTime, segun clock tick
        self.framedt = 0.0 # para controlar cuando cambiar (cycle) de frame
        self.cyclespersec = 12 # cycles a cambiar por segundo
        self.framedelta = self.cyclespersec / game.FPS
        log('DEBUG','PLAYER','move_step:',str(self.move_step),'cps:',str(self.cyclespersec),'threshold:',str(self.framedelta))
        
        self.walking = False
        self.stepxy = (0,0)

        self.image = self.images[0][0] # es de tipo pygame.Surface
        self.rect = pygame.Rect(1,1,150,198)
        #self.rect = self.image.get_rect() # Get rect of some size as 'image'.

    def loadImages(self):        
        imall = pygame.image.load(normalizePath('images/man-all.png'))
        imall = imall.convert_alpha() # TEST
        images_per_direction = 12 # en base a la imagen
        directions = 4
        w = imall.get_width()
        h = imall.get_height()
        each_w = CeilDivision(w, images_per_direction) #(w / images_per_direction)
        each_h = int(h / directions)
        xpad = 0
        ypad = 0
        for row in range(directions): # Ojo, hay que matchear cada fila con Dir
            im_row = []
            for col in range(images_per_direction): # ciclos
                left =  xpad + col * each_w
                upper = ypad + row * each_h
                surf_w = each_w #- 2 * xpad
                surf_h = each_h - ypad
                
                right = left + surf_w
                dif = w - right
                if (dif < 0): # ajuste por redondeo
                    surf_w += dif
                log('INFO','player:',w,h,left,upper,each_w,each_h,xpad,ypad,surf_w, surf_h,dif)
                
                # crop de cada subimagen
                im = imall.subsurface((left, upper, surf_w, surf_h))
                im_row.append(im)
                
            self.images.append(im_row)
        log('DEBUG',self.images)
            
    def getColor(self, x=-1, y=-1):
        # devuelve el color del mapa de la coordenada x,y (si no se pasan, se usa foot)
        if (x==-1 and y==-1):
            x = self.xfoot
            y = self.yfoot
        return self.game.getColor((x, y))

    def getScaleByColor(self, color):
        minscale = 0.1 # para que al menos siempre sea visible
        errorscale = 0.01 # si es menor a esto, hay algo raro!
        scale = getBlueColor(color) / 200 # escala del SPRITE segun tono de azul del mapa
        if scale < minscale:
            if scale < errorscale:
                scale = 0
                log('DEBUG','error scale! ',scale, ' con color ',color)
            else:
                log('DEBUG','minscale! ',scale, ' con color ',color)
                scale = minscale
        return scale    

    def isEclipsedByLayer(self, z, xfrom, xto):
        # Z es una coordenada externa que determina si se eclipsa la Y del player
        if self.yfoot < z:
            # para acotar los blits, veo que horizontalmente tambien se eclipsen
            halfw = int(self.image.get_width() / 2)
            xplayer_right = self.xfoot + halfw
            xplayer_left = self.xfoot - halfw
            if (xplayer_right > xfrom) and (xplayer_left < xto):
                return True
        return False

    def setRectByFootAndScale(self):
        # obtengo el color (R,G,B) en el mapa
        colorxy = self.getColor()
        if self.game.isPositionAllowed(colorxy):
            # Actualizo frame del sprite X veces por segundo, segun FPS
            #if self.framedt >= self.framedelta:
            newscale = self.getScaleByColor(colorxy)
            if newscale > 0:
                self.scale = newscale
            if self.scale != 1:
                self.scaleImage()
            cur_width = self.image.get_width()
            cur_height = self.image.get_height()
            x = self.xfoot - int(cur_width / 2)
            y = self.yfoot - cur_height
            self.moveRectTo(x, y)
        else:
            log('INFO','OJO, posicion prohibida!', self.xfoot, self.yfoot)

    def moveRectTo(self, x, y):
        self.rect.x = x # no funciona el metodo rect.move(x,y)
        self.rect.y = y
        #log('DEBUG','rect moved to ',x,y)

    def setPosition(self, x, y, direction):
        self.direction = direction
        self.updateImage()
        self.moveFeetTo(x, y)
        self.setRectByFootAndScale()

    def saveState(self):
        # devuelve JSON con estado actual
        state = {}
        footxy = self.getFootXY()
        state['x'] = footxy[0]
        state['y'] = footxy[1]
        state['direction'] = self.direction
        return state
        
    def loadState(self, state):
        x = state['x']
        y = state['y']
        direction = state['direction']
        self.setPosition(x, y, Dir(direction))
        
    def moveFeetTo(self, x, y):
        self.xfoot = x
        self.yfoot = y

    def getFootXY(self):
        return (self.xfoot, self.yfoot)

    def walkTo(self, waypoints):
        self.stepxy = (0,0)
        aux = waypoints.pop(0) # quito el primer wp ya que es el origen
        self.waypoints = waypoints
        self.walking = True

    def stopWalking(self):
        self.walking = False
        self.stepxy = (0,0)

    def scaleImage(self):
        cur_width = self.image.get_width()
        cur_height = self.image.get_height()
        new_width = Ceil(cur_width * self.scale)
        new_height = Ceil(cur_height * self.scale)
        dx = cur_width - new_width
        dy = cur_height - new_height
        if (dx != 0 or dy != 0):
            #log('DEBUG','scaled by ' , self.scale)
            self.image = pygame.transform.scale(self.image, (new_width, new_height))        
        
    def update(self, keys, dt):
        has_moved = False
        step = int(self.move_step * dt)
        if step > self.move_step_max:
            step = self.move_step_max
        if 1 in keys: # si hay alguna tecla presionada
            new_x = self.xfoot
            new_y = self.yfoot
            direction = Dir.none
            if keys[pygame.K_LEFT] and not keys[pygame.K_RIGHT]:
                new_x -= step
                has_moved = True
                direction = Dir.W
            if keys[pygame.K_RIGHT] and not keys[pygame.K_LEFT]:
                new_x += step
                has_moved = True
                direction = Dir.E
            if keys[pygame.K_UP] and not keys[pygame.K_DOWN]:
                new_y -= step
                has_moved = True
                #if direction == Dir.none:
                direction = Dir.N
                #elif direction == Dir.E:
                #    direction = Dir.NE
                #elif direction == Dir.W:
                #    direction = Dir.NW
            if keys[pygame.K_DOWN] and not keys[pygame.K_UP]:
                new_y += step
                has_moved = True
                #if direction == Dir.none:
                direction = Dir.S
                #elif direction == Dir.E:
                #    direction = Dir.SE
                #elif direction == Dir.W:
                #    direction = Dir.SW
                
        if self.walking:
            direction = self.direction
            if self.stepxy == (0,0): # nunca se movio o debe tomar un nuevo waypoint
                self.waypoint = self.waypoints.pop(0) # primer waypoint
                wayxy = self.getFootXY() # obtengo coord actuales
                self.wayx = wayxy[0]
                self.wayy = wayxy[1]
                dxy = deltaXY(wayxy, self.waypoint)
                self.stepxy = relStepXY(step, dxy)
                log('DEBUG','Player con nuevo waypoint',self.waypoint)
                # defino la direccion en base al deltaxy
                if abs(dxy[0]) > abs(dxy[1]): # mueve mas en X
                    if dxy[0] > 0:
                        direction = Dir.E
                    else:
                        direction = Dir.W
                else: # mueve mas en Y
                    if dxy[1] > 0:
                        direction = Dir.S
                    else:
                        direction = Dir.N
                
            # NOTA: tuples are immutable
            
            # muevo hacia el waypoint
            self.wayx = self.wayx + self.stepxy[0] # mantengo estas coord con decimales
            self.wayy = self.wayy + self.stepxy[1]
            new_x = Ceil(self.wayx)
            new_y = Ceil(self.wayy)
            # veo si ya llego al waypoint
            dist = lengthXY((new_x,new_y), self.waypoint)
            #log('DEBUG','dist',dist)
            has_moved = True
            if dist < step: # llego a un waypoint
                log('DEBUG','llego a wp:',(new_x,new_y),'dist:'+str(dist),'step:'+str(step))
                if len(self.waypoints) > 0:
                    self.stepxy = (0,0)
                else:
                    self.stopWalking()
                
        if has_moved:
            #self.framedt += dt
            self.framedt += self.framedelta
            #log('DEBUG','dt:',str(dt),'step:',step,'framedt',str(self.framedt))
            
            if self.insideScreen(new_x, new_y):
                room = self.game.changingRoomTo((new_x, new_y))
                if room > 0:
                    # convertir el numero de salida del mapa grafico a un Room
                    newRoom = self.game.rooms[self.game.currentRoom]['directions'][str(room)]
                    self.game.goToRoom(newRoom) # Interaccion entre clase Sprite y clase Game
                elif self.canMove(new_x, new_y):
                    self.direction = direction
                    self.cycleImage()                
                    self.moveFeetTo(new_x, new_y)
                    self.setRectByFootAndScale()
                #log('DEBUG',self.direction)
            else:
                has_moved = False
            if self.framedt >= self.cyclespersec:
                self.framedt = 0.0 # reinicio dt de frames
                
        if has_moved == False:
            self.stopWalking()
            
        return has_moved
    
    def cycleImage(self):
        # Actualizo frame del sprite X veces por segundo, segun FPS
        
        #if self.framedt >= self.framedelta:
        self.index = int(self.framedt)
            #self.index += 1 # siguiente frame del sprite
        if self.index >= len(self.images[int(self.direction.value)]):
            self.index = 0        
        self.updateImage()
    
    def updateImage(self):
        # actualiza la imagen actual en base a la direccion y el index
        self.image = self.images[int(self.direction)][self.index]
        
    def insideScreen(self, x, y):
        if x <= 0:
            return False
        if x >= self.game.width:
            return False
        if y <= 0:
            return False
        if y >= self.game.height:
            return False
        return True
        
    def canMove(self, x, y):
        # no permitir si sale de la pantalla
        if self.insideScreen(x, y) == False:
            return False
        # no permitir si ingresa a una zona del mapa no permitida (en negro)
        colorxy = self.getColor(x, y)
        if self.game.isPositionAllowed(colorxy) == False:
            return False        
        return True
    

class Game(object):
    def main(self, screen):
        # Variables globales
        global cached_images
        global cached_sounds

        self.screen = screen
        # En pygame:
        #  - se usa Surface para representar la "apariencia", y
        #  - se usa Rect para representar la posicion, de un objeto.
        #  - se hereda de pygame.sprite.Sprite para crear sprites, y con Group se los agrupa.

        self.width = screen.get_width()
        self.height = screen.get_height()
        
        gamename = 'Alex\'s First Graphic Adventure Game, with a twist'
        log('DEBUG','Setting caption')
        pygame.display.set_caption(gamename)
        cached_images = {}
        self.dirtyscreen = True
        # en vez de pygame.time.delay(100), usar clock para controlar los FPS
        self.FPS = 15 # Frames per second.
        # FPS <-> dt ( la constante es FPS*dt=1 )
        #  15 <-> 0.066
        #  20 <-> 0.05
        #  30 <-> 0.033
        log('DEBUG','Init clock and FPS',str(self.FPS))
        self.clock = pygame.time.Clock()
        # Message Box
        self.global_text = ''
        self.show_message = False
        self.message_time = 0
        self.previoustext = ''    
        # defining a font 
        #fontsize = int(40 / screenrel) # para default/none
        self.fontsize = int(28 / screenrel) # para Arial
        self.maxstringlength = 50
        #defaultfont =  pygame.font.get_default_font()
        #customfont = defaultfont # 'Corbel'
        #customfont = None
        self.customfont = 'Arial'
        log('DEBUG','Setting small Font',self.customfont,str(self.fontsize))
        pygame.font.init()
        self.smallfont = pygame.font.SysFont(self.customfont, self.fontsize)
        #self.borderfont = pygame.font.SysFont(self.customfont, self.fontsize+2)
        #smallfont = pygame.font.Font(customfont, fontsize)
        log('DEBUG','Setting colors')
        self.textcolor = (255, 220, 187) # RGB default textcolor
        self.cursorcolor = (187, 220, 255)
        self.backtextcolor = (170, 170, 170, 190) # fondo translucido de texto
        self.textbordercolor = (30, 30, 30)
        self.backinvcolor = (87, 27, 71, 150) # fondo translucido de inventario
        self.backitemcolor = (142, 67, 192, 190) # fondo translucido de inventario
        self.textX = self.width/3
        self.textY = self.height/3
        self.textinputX = 10
        self.textinputY = self.height-self.fontsize-13
        self.show_inventory = False
        self.currentRoom = ''
        self.run = True
        # Create TextInput-object (3rd party library)
        log('DEBUG','Init textinput')
        self.textinput = pygame_textinput.TextInput(text_color = self.textcolor, cursor_color = self.cursorcolor, font_family = self.customfont, font_size = self.fontsize, max_string_length = self.maxstringlength)
        
        log('DEBUG','Setting rooms and items')
        self.setRooms()
        self.setItems()
        
        # Cargar sonido
        #grillos = pygame.mixer.Sound('grillos.wav')
        log('DEBUG','Init sounds')
        try:
            pygame.mixer.init()
            self.musica = pygame.mixer.music
            self.has_audio = True
        except Exception as err:
            log('INFO','Error: No audio device')
            self.has_audio = False
            
        # Setup the player sprite and group
        self.player = Player(self)
        self.sprites = pygame.sprite.Group(self.player)
        # start the player in the first room
        self.goToRoom('Forest') # Primer room de la lista    
        # draw the initial screen
        self.draw_screen()
        self.keys_allowed = True
        
        # and let the game begin
        self.gameLoop()

    def doQuit(self):
        # Desactivar sonido y video, y salir
        self.globalMessage(rndStrMemory(['Bye bye!','We\'ll miss you...','Don\'t be frustrated. You\'ll make it next time.','Is it bedtime already?']))
        self.draw_screen()
        sleep(1)
        if self.has_audio:
            self.musica.stop()
        pygame.quit()
        quit()

    def drawText(self, texto, color, x, y):
        textosurf = self.smallfont.render(texto , True , color)
        self.screen.blit(textosurf, (x, y) )

    def drawTextOutline(self, texto : str, color, bordercolor, x, y, bold : bool, outline: int, centeredxy = False):
        font = self.smallfont
        font.set_bold(bold)        
        if outline > 0:
            outlineSurf = font.render(texto, True, bordercolor)
            outlineSize = outlineSurf.get_size()
            textSurf = pygame.Surface((outlineSize[0] + outline*2, outlineSize[1] + 2*outline))
            textRect = textSurf.get_rect()
            offsets = [(ox, oy) 
                for ox in range(-outline, 2*outline, outline)
                for oy in range(-outline, 2*outline, outline)
                if ox != 0 or ox != 0]
            for ox, oy in offsets:   
                px, py = textRect.center
                textSurf.blit(outlineSurf, outlineSurf.get_rect(center = (px+ox, py+oy))) 
            innerText = font.render(texto, True, color).convert_alpha()
            textSurf.blit(innerText, innerText.get_rect(center = textRect.center)) 
        else:
            textSurf = font.render(texto, True, color)
            textRect = textSurf.get_rect()    

        BLACK = (0, 0, 0) # sin esto, aparece un fondo negro
        textSurf.set_colorkey(BLACK) # Black colors will not be blit.

        if centeredxy:
            textRect.center = (x,y)
        else:
            textRect.x = x
            textRect.y = y
        self.screen.blit(textSurf, textRect)

    def getColor(self, coord):
        # devuelve el color del mapa de la coordenada (x,y)
        return self.screenmap.get_at( coord )

    def changingRoomTo(self, coord):
        color = self.getColor(coord)
        G = getGreenColor(color)
        # G = 200 + room_number * 10 + descarte (tomo la decena)
        if (G == 0) or (G < 200): 
            return 0 # no cambia de room
        room = (G - 200) // 10
        return room

    def isPositionAllowed(self, color):
        B = getBlueColor(color)
        if B == 0: # B=0 es una posicion prohibida, no debiera llegar aca!
            return False
        if self.isPositionBlocked(color):
            return False # blocking object active, cant pass throught!
        return True

    def isAllowedOrExit(self, coord):
        allowed = self.isPositionAllowed(self.getColor( coord ))
        if not allowed:
            room = self.changingRoomTo(coord)
            if room > 0:
                allowed = True
        return allowed

    def isPositionBlocked(self, color):
        # La posicion puede estar bloqueada (color verde del mapa)
        G = getGreenColor(color)
        if (G > 100) and (G < 200): 
            blockid = (G - 100) // 10 # decena del color verde
            log('DEBUG','block id: ',blockid)
            if self.rooms[self.currentRoom]['blockages'][str(blockid)]['active'] == True:
                return True
        return False

    def getExitPoint(self, roomnumber): # asumo que tiene, y devuelvo coord
        return self.rooms[self.currentRoom]['exitpoints'][str(roomnumber)]
    
    def findWaypoints(self, xyFrom, xyTo):
        # custom Pathfinding
        wp = []
        wp.append(xyFrom) # el primer waypoint siempre es el origen

        room = 0
        allowed = self.isAllowedOrExit(xyTo)
        if allowed:
            room = self.changingRoomTo(xyTo)
        blocked, blockage, block = self.findBlockPoint(xyFrom, xyTo)
        has_helperwp = 'waypoints' in self.rooms[self.currentRoom]
        
        log('DEBUG','allowed:'+str(allowed),'blocked:'+str(blocked),'room:'+str(room),'blockage:'+str(blockage))
        
        if allowed:
            if (room > 0):
                exitpoint = self.getExitPoint(room)
                if blocked:
                    if has_helperwp: # Si el room tiene waypoints
                        log('DEBUG','USO WAYPOINTs y EXIT')
                        wp = self.addHelperWaypoints(wp, xyFrom, xyTo)
                        wp.append(exitpoint) 
                    else:
                        log('DEBUG','HASTA BLOCK')
                        wp.append(block)
                else:
                    log('DEBUG','EXIT directo')
                    wp.append(exitpoint)
            else:
                if blocked:
                    if blockage: # blockage
                        log('DEBUG','HASTA BLOCKAGE')
                        wp.append(block)
                    else:
                        if has_helperwp: # Si el room tiene waypoints
                            log('DEBUG','USO WAYPOINTs')
                            wp = self.addHelperWaypoints(wp, xyFrom, xyTo)
                            wp.append(xyTo)
                        else:
                            log('DEBUG','HASTA BLOCKAGE')
                            wp.append(block)
                else:
                    log('DEBUG','NORMAL')
                    wp.append(xyTo)
        else:
            log('DEBUG','HASTA BLOCK')
            wp.append(block)
            
        if True: # quitar para no mostrar waypoints
            for i in range(1, len(wp)):
                log('DEBUG','waypoint '+str(i), 'from ',wp[i-1],'to ',wp[i])            
                if log_level != 'NONE':
                    pygame.draw.line(self.screen, (int(random.uniform(1,254)), 30+(i-1)*40, 40+i*40), wp[i-1], wp[i], 2)
                    pygame.display.update()
                    sleep(1)
        return wp
    
    def addHelperWaypoints(self, current_wps, xyFrom, xyTo):
        # De la lista de waypoints del room, agrego los necesarios para
        #  llegar de xyFrom a xyTo        
        helperwp = self.rooms[self.currentRoom]['waypoints']
        cant = len(helperwp)
        if cant == 1:
            current_wps.append(helperwp[0])
            return current_wps
        else:
            # De la lista de waypoints del room, ir ordenandolos por cercania al Destino;
            ordwp = orderedCoordsTo(helperwp, xyTo)
            # luego ver si esta bloqueado el camino desde Origen hasta cada wp.
            # - Mientras este bloqueado, agregarlo al final de la lista de wp actuales, y seguir.
            # - Si no esta bloqueado, agregarlo al final, y salir.        
            for i in range(cant):
                blocked, blockage, block = self.findBlockPoint(xyFrom, ordwp[i])
                if blocked or blockage:
                    #current_wps.append(ordwp[i])
                    current_wps.insert(1, ordwp[i]) # por simplicidad siempre inserto en el segundo lugar
            current_wps.insert(1,ordwp[cant-1])
            return current_wps

    def findWaypointsXXX(self, xyFrom, xyTo):
        # custom Pathfinding
        wp = []
        wp.append(xyFrom) # el primer waypoint siempre es el origen
        
        #dest_allowed = self.isPositionAllowed(self.getColor( xyTo )) # veo si el destino final esta permitido
        dest_allowed = self.isAllowedOrExit( xyTo ) # veo si el destino final esta permitido
        if dest_allowed:            
            # buscar bloqueos
            wp = self.addHelperWaypointsIfBlocked(wp, xyFrom, xyTo)            
            wp.append(xyTo) # el ultimo waypoint siempre es el destino
        else:
            # intento moverme horizontal o verticalmente
            tryTo = (xyTo[0], xyFrom[1])
            dest_allowed = self.isAllowedOrExit( xyTo )
            log('DEBUG','intento 1',tryTo,dest_allowed)
            if dest_allowed:
                wp.append(tryTo)
            else:
                tryTo = (xyFrom[0], xyTo[1])
                dest_allowed = self.isAllowedOrExit( xyTo )
                log('DEBUG','intento 2',tryTo,dest_allowed)
                if dest_allowed:
                    wp.append(tryTo)
                else:
                    log('DEBUG','No se encontro waypoint, por ahora solo voy al helper')
                    wp = self.addHelperWaypointsIfBlocked(wp, xyFrom, xyTo)
                    # intento moverme, de nuevo, horizontal o verticalmente
                    tryTo = (xyTo[0], wp[len(wp)-1][1])                    
                    dest_allowed = self.isAllowedOrExit( xyTo )
                    log('DEBUG','intento 3',tryTo,dest_allowed)
                    if dest_allowed:
                        wp.append(tryTo)
                    else:
                        tryTo = (wp[len(wp)-1][0], xyTo[1])
                        dest_allowed = self.isAllowedOrExit( xyTo )
                        log('DEBUG','intento 4',tryTo,dest_allowed)
                        if dest_allowed:
                            wp.append(tryTo)
                        else:
                            log('DEBUG','NO, no se encontro waypoint')

        if True: # quitar para no mostrar waypoints
            for i in range(1, len(wp)):
                log('DEBUG','waypoint '+str(i), 'from ',wp[i-1],'to ',wp[i])            
                if log_level != 'NONE':
                    pygame.draw.line(self.screen, (int(random.uniform(1,254)), 30+(i-1)*40, 40+i*60), wp[i-1], wp[i], 2)
                    pygame.display.update()
                    sleep(1)
        return wp

    def addHelperWaypointsIfBlocked(self, wp, xyFrom, xyTo):
        blocked, blockage, block = self.findBlockPoint(xyFrom, xyTo)        
        if blocked:
            log('DEBUG','BLOCKED!')
            # ante un bloqueo, utilizo helper waypoints (distintos por cada room)
            if 'waypoints' in self.rooms[self.currentRoom]:
                log('DEBUG','Looking for helper waypoints')
                waypoints = self.rooms[self.currentRoom]['waypoints']
                log('DEBUG','there are ',len(waypoints),'helpers')
                for i in range(len(waypoints)):
                    log('DEBUG','helper #',i,waypoints[i])
                    if i == 0: # aca ver cual conviene
                        wp.append(waypoints[i])
                        log('DEBUG','Helper waypoint',waypoints[i])
            else: # TODO
                wp.append(block) # agrego waypoints
    
        return wp
    
    def findBlockPoint(self, xyFrom, xyTo):
        #dx = xyTo[0] - xyFrom[0] # delta X
        #dy = xyTo[1] - xyFrom[1] # delta Y
        dxy = deltaXY(xyFrom, xyTo)
        step = 5 # OJO repetido del player!
        stepxy = relStepXY(step, dxy)
        stepx = stepxy[0]
        stepy = stepxy[1]
        # valor inicial
        blockx = xyFrom[0]
        blocky = xyFrom[1]
        allowed = True
        blockage = False
        dist = abs(stepx) + abs(stepy) + 10 # solo para que entre al loop
        pos = (int(blockx), int(blocky))
        #log('DEBUG','findBlockPoint',xyFrom, xyTo, rel, dx, dy, stepx, stepy)
        while (dist > abs(stepy)) and (dist > abs(stepx)) and (allowed == True):
            blockx += stepx
            blocky += stepy
            pos = (int(blockx), int(blocky))
            if log_level != 'NONE':
                pygame.draw.circle(self.screen, (200,0,0), pos, 3, 0)
            # veo si bloquea este punto
            color = self.getColor( pos )
            allowed = self.isPositionAllowed(color)
            if allowed:
                blockage = self.isPositionBlocked(color) # blocked by active blockages
                allowed = not blockage
            else:
                log('DEBUG','Cambio a NOT ALLOWED',pos,color)
                
            dist = abs(blockx - xyTo[0])
            log('DEBUG','findBlockPoint',pos,allowed,dist)
            
        if log_level != 'NONE':
            pygame.display.update()
        blocked = not allowed
        # Devuelve:
        #  blocked (bool): Si se encuentra el camino bloqueado
        #  blockage (bool): Si el bloqueo es por un blockage (que podria desactivarse)
        #  pos (tupla): posicion de choque
        return blocked, blockage, pos        

    
    def globalMessage(self,texto):
        #self.global_text = filter_nonprintable(texto)
        self.global_text = texto
        self.show_message = True
        self.dirtyscreen = True
        self.message_time = int(2 + math.sqrt(len(self.global_text)) * (self.FPS/2)) # tiempo en pantala proporcional al texto

    def updateMessage(self):
        self.message_time -= 1
        if self.message_time == 0:
            self.show_message = False # si la cuenta regresiva termino, quitar mensaje

    def drawMessage(self):
        con_recuadro = False
        ancho_recuadro = 40 # en caracteres
        aspectw = int(14 / screenrel)
        # TODO: Arreglar ancho cuando hay 2 renglones desproporcionados
        wrappedlines = textwrap.wrap(self.global_text, ancho_recuadro, replace_whitespace=False)
        lineas_recuadro = len(wrappedlines)
        dw = 5 # delta/margen de ancho
        dh = 5 # delta/margen de alto
        maxlen = 0
        for line in wrappedlines: # obtengo ancho maximo
            if len(line) > maxlen:
                maxlen = len(line)
        #w = (len(global_text)*aspectw + dw) / lineas_recuadro # ancho de la caja de texto (teniendo en cuenta wrap)
        w = int(maxlen * aspectw) + dw
        fh = self.fontsize + dh + 4 # alto de una linea de texto
        h = fh * lineas_recuadro # altura total del recuadro (teniendo en cuenta wrap)
        x = self.width/2 - w/2
        y = self.height/2 - h/2
        if con_recuadro:
            self.drawRect(x,y,w,h,self.backtextcolor) # recuadro de fondo
        i = 0
        for line in wrappedlines:
            #self.drawText(line, self.textcolor, x+dw, y+dh+i*fh)
            self.drawTextOutline(line, self.textcolor, self.textbordercolor, x+dw, y+dh+i*fh, True, 2)
            i = i + 1

    def procesarComando(self, comando):
        words = comando.lower().split()
        if words[0] in ('quit','salir'):
            self.doQuit()
        if words[0] in ('help','ayuda','?'):
            self.showHelp()
        elif words[0] == 'save':
            self.saveGame()
            self.globalMessage('Game saved')
        elif words[0] == 'load':
            if self.loadGame():
                self.globalMessage('Game loaded')
            else:
                self.globalMessage('You have not saved any game before')
        #some fun
        elif words[0] == 'jump':
            self.globalMessage(rndStrMemory(['There is no jumping in this game','This is Kaos. We don\'t jump here!','Jump! Jump! Here comes the man...','You feel exhausted just by thinking of jumping','Wrong game for jumping I think']))
        elif words[0] == 'dive':
            self.globalMessage(rndStrMemory(['Are you nuts?','You should change your pills.','No diving in this area!','There are better moments for diving','I don\'t have my snorkel']))
        elif words[0] == 'sit':
            self.globalMessage(rndStrMemory(['There is no time to be wasting','Walking is good for your health.','Nah, I don\'t wan\'t to sit, thanks.','Sit? Am I a dog?','Is that what will let you out of this forest?']))
        elif words[0] == 'sleep':
            self.globalMessage(rndStrMemory(['Come on you lazy cow!','There is no time for a nap','No! Wake up!','Definitely not!','Let me think... no!','Bored already?']))
        elif words[0] in ('talk','scream','shout'):
            self.globalMessage(rndStrMemory(['Shhh!','No one can hear you','There is no one around','There is no use in talking, screaming or shouting']))
        elif words[0] in ('look','mirar','ver'):
            if len(words) == 1:
                self.comandoLookRoom()
            else:
                self.comandoLookItem(words[1])
        elif words[0] in ('get','take','grab','agarrar'):
            if len(words) > 1:
                itemstr = words[1]
                self.comandoGetItem(itemstr)
        elif (words[0] in ('go','ir')) and (len(words)>1):
            #self.comandoGoRoom(words[1])
            self.globalMessage(rndStrMemory(['Deprecated command, just walk','Walking works just fine','Go, go, go!','Games evolve','By "go" you mean the ancient board game?']))
        elif (words[0] == 'use') and (len(words)>3) and (words[2] == 'with'):
            self.comandoUse(words[1], words[3])
        else:
            self.globalMessage(rndStrMemory(['Incorrect command','Not sure what you mean','Try something else','Hit F1 key for help on commands','That does not compute']))

    def showHelp(self):
    #2345678901234567890123456789012345678901234567890123456789012345678901234567890
        helpmessage = """               -< Command Help >-                                        
        look : describes what's around you.                                             
        look [item] : describes an item in your inventory or in the room.               
        get [item] : takes an object of the room and keeps it in your inventory.        
        use [item] with [item] : tries to make an interaction between the two items.    
        save : records your game so you can play some other day.                     
        load : restores the game that you had saved before.                         
        F3 : repeats last command.                                                      
        TAB : shows your inventory.                                                     
        """
        self.globalMessage(helpmessage)
        
    def comandoGoRoom(self,direction):
        #check that they are allowed wherever they want to go
        if direction in rooms[currentRoom]['directions']:
            #set the current room to the new room
            goToRoom( rooms[currentRoom]['directions'][direction] )
        else: # there is no door (link) to the new room
            self.globalMessage(rndStrMemory(['You can\'t go that way!','Really? '+direction+'?','Consider getting a compass','I don\'t think going that way is the right way','Danger! Going that way is demential (because it doesn\'t exists)']))

    def comandoLookRoom(self):
        # mostrar descripcion del room actual, y posibles salidas
        mensaje = self.rooms[self.currentRoom]['desc']
        # mostrar los items que hay en el room actual
        if bool(self.rooms[self.currentRoom]['items']):
            mensaje += ' You see '
            i = 0
            cantitems = len(list(self.rooms[self.currentRoom]['items']))
            for item in self.rooms[self.currentRoom]['items']:
                i += 1
                if (self.rooms[self.currentRoom]['items'][item]['visible'] == True):
                    if i > 1:
                        mensaje += ', '
                        if cantitems == i:
                            mensaje += 'and '
                    mensaje += self.rooms[self.currentRoom]['items'][item]['roomdesc']
                else:
                    i -= 1
                    cantitems -= 1
            mensaje += '.                                          '
        
        #moves = rooms[currentRoom]['directions'].keys()
        #movelist = list(moves)
        #cantmoves = len(movelist)
        #if cantmoves == 1:
        #    mensaje += 'Your only move is ' + movelist[0]
        #else:
        #    mensaje += 'Your possible moves are '
            #i = 0
        #    for i in range(cantmoves):
                #i += 1
        #        if i > 0:
        #            if cantmoves-1 == i:
        #                mensaje += ' and '
        #            else:
        #                mensaje += ', '
        #        mensaje += movelist[i]
        #    mensaje += '.'
        
        self.globalMessage(mensaje)

    def comandoLookItem(self,itemstr):
        # el item a mirar puede estar en el inventario o en el room actual
        if (itemstr in self.inventory.keys()): # si el item lo tengo yo
            mensaje = self.inventory[itemstr]['desc']
        else:
            if (itemstr in self.rooms[self.currentRoom]['items'].keys()): # si el item esta en el room
                if (self.rooms[self.currentRoom]['items'][itemstr]['takeable'] == True):
                    mensaje = 'You see ' + self.rooms[self.currentRoom]['items'][itemstr]['roomdesc']
                else:
                    if self.rooms[self.currentRoom]['items'][itemstr]['visible'] == True:
                        if ('locked' in self.rooms[self.currentRoom]['items'][itemstr]) and (self.rooms[self.currentRoom]['items'][itemstr]['locked'] == False) and (self.rooms[self.currentRoom]['items'][itemstr]['iteminside'] in self.rooms[self.currentRoom]['items'].keys()):
                            mensaje = 'You see ' + self.rooms[self.currentRoom]['items'][itemstr]['roomdescunlocked']
                        else:
                            mensaje = 'You see ' + self.rooms[self.currentRoom]['items'][itemstr]['desc']
                    else:
                        mensaje = rndStrMemory(['I don\'t see any ' + itemstr, 'It may have dissapeared, you know.','Are you sure the '+ itemstr +' is still there?'])
            else:
                if (itemstr in self.rooms[self.currentRoom]['directions'].keys()):
                    mensaje = 'Yes, you can go ' + itemstr
                else:
                    mensaje = rndStrMemory(['The ' + itemstr + ' is not here' , 'I don\'t see any ' + itemstr])
        self.globalMessage(mensaje)

    def comandoGetItem(self,itemstr):
        if (itemstr in self.inventory.keys()):
            mensaje = 'You already have the ' + itemstr
        else:
            if (itemstr in self.rooms[self.currentRoom]['items']) and (self.rooms[self.currentRoom]['items'][itemstr]['visible'] == True):
                if (self.rooms[self.currentRoom]['items'][itemstr]['takeable']):
                    #add the item to their inventory
                    self.inventory[itemstr] = self.rooms[self.currentRoom]['items'][itemstr]
                    #display a helpful message
                    mensaje = rndStrMemory([itemstr + ' got!','Yeah! You have gotten the '+itemstr,'The '+itemstr+', just what you\'ve been looking for','At last, the glorious '+itemstr ])
                    #delete the item from the room
                    del self.rooms[self.currentRoom]['items'][itemstr]
                else:
                    mensaje = rndStrMemory(['You can\'t get the ' + itemstr, 'Nah! It\'s like painted to the background', 'You wish!'])
            else:
                #tell them they can't get it
                mensaje = rndStrMemory([itemstr + ' is not here', 'Nah!', 'You wish!'])
        self.globalMessage(mensaje)
        
    def comandoUse(self,item1, item2):
        # item1 debe estar en el inventory
        # item2 puede estar en el room (para accionar algo) o en el inventory (para mezclarlos)
        if (item1 in self.inventory.keys()):
            if (item2 in self.inventory.keys()): # mezclar 2 items del inventory
                if ('mixwith' in self.inventory[item1]) and ('mixwith' in self.inventory[item2])==True and (self.inventory[item1]['mixwith']['otheritem'] == item2) and (self.inventory[item2]['mixwith']['otheritem'] == item1):
                    # creo el nuevo item
                    nuevoitem = self.inventory[item2]['mixwith']['summon']
                    self.inventory[nuevoitem] = self.ghostitems[nuevoitem]
                    # delete both original items from the inventory
                    del self.inventory[item1]
                    del self.inventory[item2]
                    del self.ghostitems[nuevoitem]
                    #display a helpful message
                    #globalMessage('summoned a ' + nuevoitem)
                    mensaje = self.inventory[nuevoitem]['summonmessage']
                else:
                    mensaje = rndStrMemory(['Can\'t use ' + item1 + ' with ' + item2 + '!','I don\'t think the '+item1+' is meant to be used with the '+item2,'...'+item1+' with '+item2+' does not compute.'])
            elif (item2 in self.rooms[self.currentRoom]['items']): # accionar algo que esta 'locked'
                if ('locked' in self.rooms[self.currentRoom]['items'][item2]):
                    if (self.rooms[self.currentRoom]['items'][item2]['locked'] == True):
                        if (item1 == self.rooms[self.currentRoom]['items'][item2]['unlockeritem']):
                            # al accionar item2 con item1, queda visible iteminside
                            self.rooms[self.currentRoom]['items'][item2]['locked'] = False # lo destrabo y queda asi
                            if ('iteminside' in self.rooms[self.currentRoom]['items'][item2]):
                                iteminside = self.rooms[self.currentRoom]['items'][item2]['iteminside']
                                self.rooms[self.currentRoom]['items'][iteminside]['visible'] = True # descubro el iteminside
                                mensaje = self.rooms[self.currentRoom]['items'][item2]['unlockingtext']
                            else:
                                mensaje = 'OJO: el iteminside no esta en '+self.currentRoom # no debiera llegar aca
                        else:
                            mensaje = 'I think the '+item1+' is not meant to be used with the '+item2+'.'
                    else:
                        mensaje = rndStrMemory(['Not again!','You\'ve already done that.','Don\'t be repetitive dude!'])
                elif ('blocked' in self.rooms[self.currentRoom]['items'][item2]): # destrabar algo para poder pasar
                    if (self.rooms[self.currentRoom]['items'][item2]['blocked'] == True):
                        if (item1 == self.rooms[self.currentRoom]['items'][item2]['unlockeritem']):
                            self.rooms[self.currentRoom]['items'][item2]['blocked'] = False # destrabo el bloqueo y queda asi
                            self.rooms[self.currentRoom]['items'][item2]['visible'] = False # ya no se ve el bloqueo
                            blockid = self.rooms[self.currentRoom]['items'][item2]['blockid'] # ID del blockage
                            self.rooms[self.currentRoom]['blockages'][blockid]['active'] = False # libero el bloqueo para que el player pueda pasar
                            mensaje = self.rooms[self.currentRoom]['items'][item2]['unlockingtext']
                        else:
                            mensaje = 'I think the '+item1+' is not meant to be used with the '+item2+'.'
                    else:
                        mensaje = rndStrMemory(['Are you still seeing that?','You\'ve already done that.','Don\'t be repetitive pal!'])
                else:
                    mensaje = rndStrMemory(['Can\'t use ' + item1 + ' with ' + item2 + '!','I don\'t think the '+item1+' is meant to be used with the '+item2,'...'+item1+' with '+item2+' does not compute.'])
            else:
                mensaje = rndStrMemory(['There is no ' + item2 + ' around.', 'Try something else.'])
        else:
            mensaje = 'You don\'t have any ' + item1
        self.globalMessage(mensaje)

    def loadMusic(self,musicpath):
        musicpath_ok = normalizePath(musicpath)
        if self.has_audio:
            self.musica.load(musicpath_ok)

    def goToRoom(self,newroom):
        self.keys_allowed = False
        self.player.stopWalking()
        # Cargar fondo en memoria y redimensionarlo para que ocupe la ventana
        backimage = self.rooms[newroom]['background']
        self.background = pygame.image.load(normalizePath(backimage))
        self.background = self.background.convert() # TEST
        bckw = self.background.get_width()
        bckh = self.background.get_height()
        self.bckwrel = bckw / self.width
        self.bckhrel = bckh / self.height
        log('INFO','background original size:', bckw, bckh, self.bckwrel, self.bckhrel, self.width, self.height)
        self.background = pygame.transform.scale(self.background, (self.width, self.height)) # devuelve Surface
        # Cargar el mapa de escalas correspondiente al fondo
        imagemap = self.rooms[newroom]['imagemap']
        self.screenmap = pygame.image.load(normalizePath(imagemap))
        self.screenmap = self.screenmap.convert()
        self.screenmap = pygame.transform.scale(self.screenmap, (self.width, self.height)) # devuelve Surface
        # Cargar musica de fondo del room
        tema = self.rooms[newroom]['music']
        #print ('yendo de ' + currentRoom + ' a ' + newroom + ' con tema ' + tema)
        #musica.load(tema)
        if self.has_audio:
            self.loadMusic(tema)
            self.musica.play(-1) # If the loops is -1 then the music will repeat indefinitely.
            
        # obtengo coordenadas y direction del player al ingresar a este room desde el anterior
        if (self.currentRoom in self.rooms[newroom]['from']): # si no existe es porque hice loadGame
            coords = self.rooms[newroom]['from'][self.currentRoom]    
            log('INFO','Yendo de ',self.currentRoom,' a ',newroom, coords)
            #textcolor = (34, 120, 87)
            # convertir coordenadas externas a internas
            x = self.relativeW(coords[0])
            y = self.relativeH(coords[1])
            self.player.setPosition(x, y, coords[2])
        self.currentRoom = newroom
        self.keys_allowed = True
        
    def relativeW(self,x):
        #log('DEBUG','relativeW: ', x, self.bckwrel, int(x / self.bckwrel))
        return int(x / self.bckwrel)
        
    def relativeH(self,y):
        #log('DEBUG','relativeH: ', y, self.bckhrel, int(y / self.bckhrel))
        return int(y / self.bckhrel)

    def drawRect(self,x,y,w,h,color):
        surf = pygame.Surface([w, h], pygame.SRCALPHA)
        surf.fill(color)
        self.screen.blit(surf, [x,y,w,h])

    def drawItem(self,x,y,w,h,itemimagefile):
        itemimage = loadImage(itemimagefile, int(w), int(h))
        self.screen.blit(itemimage, (x, y))

    def drawInventory(self):
        # si no tengo nada en el inventario, mostrar mensaje
        if bool(self.inventory) == False:
            self.globalMessage(rndStrMemory(['You are carrying nothing!', 'Nothing in your pockets so far', 'Maybe if you start using the "get" command...']))
        else:
            itemsperrow = 2 # max columns
            listaitems = list(self.inventory)
            cantitems = len(listaitems)
            rows = CeilDivision(cantitems, itemsperrow)
            if cantitems > itemsperrow:
                cols = itemsperrow
            else:
                cols = cantitems
            pad = 5 # pixels de padding entre objetos
            aspectw = 9
            aspecth = 8
            itemw = Ceil(self.width/aspectw)
            itemh = Ceil(self.height/aspecth)
            # calcular recuadro en funcion a la cantidad de items
            fontheight = self.fontsize + 4
            xback = 10
            yback = 10
            wback = (itemw + 2*pad) * cols
            hback = (itemh + 2*pad + fontheight) * rows
            self.drawRect(xback,yback,wback,hback,self.backinvcolor) # recuadro de fondo 
            
            i = 0 # indice del item en la lista de items
            for r in range(0,rows): # por cada fila del cuadro (comienza desde cero)
                for c in range(0,cols): # por cada columna del cuadro (comienza desde cero)
                    if i < cantitems:
                        x = (xback + pad) + (itemw + pad) * c
                        y = (yback + pad) + (itemh + pad + fontheight) * r
                        self.drawRect(x,y,itemw,itemh,self.backitemcolor) # recuadro del item
                        imagefile = self.inventory[listaitems[i]]['image']
                        self.drawItem(x,y,itemw,itemh,imagefile)
                        xt = x
                        yt = y + itemh + pad
                        item = listaitems[i]
                        self.drawText(item, self.textcolor, xt, yt)
                    i += 1

    # Mostrar fondo
    def draw_screen(self):
        # pintar fondo del room en la pantalla
        self.screen.blit(self.background, (0, 0))
        #screen.blit(text, (textX, textY) )

        # dibujar bloqueos activos
        self.draw_blockages()

        # Actualizar sprites
        self.sprites.draw(self.screen)

        # Superponer layers de objetos que tapen al player
        self.draw_layers()

        # Caja translucida para el textInput
        self.drawRect(self.textinputX-3, self.textinputY-3, self.maxstringlength*9, self.fontsize+8, self.backtextcolor)
        # Blit textInput surface onto the screen
        self.screen.blit(self.textinput.get_surface(), (self.textinputX, self.textinputY))

        # ver donde estan los pies
        #footxy = player.getFootXY()
        #pygame.draw.circle(screen, (255,0,0), (footxy[0],footxy[1]), 3)
        
        # Si el inventario esta activo, mostrarlo
        if self.show_inventory == True:
            self.drawInventory()
        # Si hay un mensaje global, mostrarlo
        if self.show_message == True:
            self.drawMessage()
        # Actualizar pantalla con los elementos de screen
        pygame.display.update()

    def draw_layers(self):
        if ('layers' in self.rooms[self.currentRoom].keys()):
        #if bool(rooms[currentRoom]['layers']):
            layers = self.rooms[self.currentRoom]['layers']
            for layer in layers:
                #print ( layer )
                #print ( layers[layer]['z'] )
                z = self.relativeH( layers[layer]['z'] )
                xfrom = self.relativeW( layers[layer]['xfrom'] )
                xto = self.relativeW( layers[layer]['xto'] )
                layerimage = layers[layer]['layerimage']
                # determino si el player se superpone con este layer
                if self.player.isEclipsedByLayer(z, xfrom, xto):
                    #log('DEBUG','layer:'+layer,z,xfrom,xto,layerimage)
                    imlayer = loadImage(layerimage, self.width, self.height) # devuelve Surface
                    self.screen.blit(imlayer, (0, 0))

    def draw_blockages(self):
        if ('blockages' in self.rooms[self.currentRoom].keys()):
            blockages = self.rooms[self.currentRoom]['blockages']
            for blockage in blockages:
                active = blockages[blockage]['active']
                # solo dibujo los bloqueos activos
                if active == True:
                    blockimage = blockages[blockage]['blockimage']
                    imblock = loadImage(blockimage, self.width, self.height) # devuelve Surface
                    self.screen.blit(imblock, (0, 0))
                        
    # A dictionary linking a room to other rooms. Properties:
    # * Room
    #   - desc: to describe the room or item. [begins with Uppercase and ends with dot]
    #   - background : image of the room.
    #   - directions: where to go from this room. Numbered such as they will be decens in Green.
    #   - from: each from-room key has a vector of [x, y, Dir] with the origin position.
    #   - music: background mp3 music for this room
    #   * layers: Things that eclipse the player. Each object-key has:
    #     - z: height from which the object will eclipse the player.
    #     - xfrom and xto: restricts eclipse whithin some width range.
    #     - layerimage: transparent image (png same size as background) to blit and eclipse the player.
    #   * Item
    #     - image: image to display in the inventory
    #     - roomdesc: brief description of the item while still in the room (and is visible)
    #     - desc: item description
    #     - descwords: different words (synonims) that match the item 
    #     - takeable: whether this item can ba taken and put in our inventory.
    #       - if the item is not takeable, describe it with 'desc' key instead of roomdesc.
    #     - openable: Para cajas, cajones, puertas.
    #     - locked: Si es True, para poder abrirse con 'open' primero hay que usar el 'unlockeritem'
    #     - unlockeritem: el item de inventario a usar para destrabar y poder abrir este item/objeto de room.
    #     - unlockingtext: El mensaje a mostrar al destrabar un item/objeto de room.
    #     - iteminside: Es otro item que hay dentro (esta en el room), y queda visible en el room si es abierto este.
    #     - roomdescunlocked: text to show when, having a 'locked' key, it is False.
    #     - visible: Indica si un item en el room es visible. Si no lo es, antes hay que abrir otro item.
    #     - mixwith: el otro item con el cual me puedo mergear y summonear uno nuevo (del ghostdict)
    #     - opened: Indica si el item esta abierto.
    def setRooms(self):
        self.rooms = {
            'Forest' : {
                'desc' : 'You are in a deep and millenary forest.',
                'background' : 'images/bosque.jpg',
                'imagemap' : 'images/bosque_map.jpg',
                'directions' : {
                   '1' : 'Beach',
                   '2' : 'ForestBif'
                  },
                'from' : {
                    '' : [110, 1000, Dir.E],
                    'ForestBif' : [110, 1000, Dir.E],
                    'Beach' : [1825, 1040, Dir.W]
                    },
                'waypoints' : [(623, 474)],
                'exitpoints' : {
                    '1' : (848,489),
                    '2' : (5,479)
                    },
                'music' : 'sounds/grillos.ogg',
                'items' : {
                   'stick' : {
                       'image' : 'images/stick.png',
                       'roomdesc' : 'a stick',
                       'desc' : 'A heavy and strong wood stick',
                       'descwords' : ['branch','stick'],
                       'visible' : True,
                       'mixwith' : {
                           'otheritem' : 'knife',
                           'summon' : 'bayonet'
                           },
                       'takeable' : True
                       },
                   'bushes' : {
                       'roomdesc' : 'some bushes',
                       'desc' : 'a few thick bushes that may conceal something',
                       'descwords' : ['bush','bushes'],
                       'locked' : True,
                       'unlockeritem' : 'bayonet',
                       'unlockingtext' : 'You have cut through the bushes and uncovered something.',
                       'iteminside' : 'key',
                       'roomdescunlocked' : 'chopped bushes that now shows a key laying in the grass',
                       'visible' : True,
                       'opened' : True,
                       'openable' : False,
                       'takeable' : False
                       },
                   'key' : {
                       'image' : 'images/key.png',
                       'roomdesc' : 'a key behind the bushes',
                       'desc' : 'It\'s a golden key',
                       'descwords' : ['key'],
                       'visible' : False,
                       'mixwith' : {
                           'otheritem' : 'script',
                           'summon' : 'spell'
                           },
                       'takeable' : True
                            }
                  }
                },
            'Beach' : {
                'desc' : 'This is a quiet and sunny beach.',
                'background' : 'images/playa-isla.jpg',
                'imagemap' : 'images/playa-isla_map.jpg',
                'directions' : {
                   '1' : 'Forest',
                   '2' : 'Deck'
                  },
                'from' : {
                    'Forest' : [75, 970, Dir.E],
                    'Deck' : [550, 1020, Dir.W]
                    },
                'exitpoints' : {
                    '1' : (1,467),
                    '2' : (153,508)
                    },
                'music' : 'sounds/seawaves.ogg',
                'items' : {
                   'sand' : {
                       'image' : 'images/sand.png',
                       'desc' : 'Just, you know, sand.',
                       'visible' : True,
                       'roomdesc' : 'sand',
                       'mixwith' : {
                           'otheritem' : 'paper',
                           'summon' : 'papyrus'
                           },
                       'takeable' : True
                    }
                  }
                },
            'ForestZZ' : {
                'desc' : 'This part of the forest feels a bit dizzy.',
                'background' : 'images/bosqueZZ.jpg',
                'imagemap' : 'images/bosqueZZ_map.jpg',
                'directions' : {
                   '1' : 'ForestBif',
                   '2' : 'Mill'
                  },
                'from' : {
                    'ForestBif' : [780, 723, Dir.S],
                    'Mill' : [705, 1020, Dir.N]
                    },
                'waypoints' : [(242, 437),(313,403),(376, 378),(337, 349)],
                'exitpoints' : {
                    '1' : (357,323),
                    '2' : (291,505)
                    },
                'music' : 'sounds/grillos.ogg',
                'items' : {
                   'knife' : {
                       'image' : 'images/knife.png',
                       'roomdesc' : 'a knife beneath the tree',
                       'desc' : 'Some rusty knife',
                       'descwords' : ['knife','blade','cutter'],
                       'visible' : True,
                       'mixwith' : {
                           'otheritem' : 'stick',
                           'summon' : 'bayonet'
                           },
                       'takeable' : True
                       }              
                  }
                },
            'ForestBif' : {
                'desc' : 'The same forest with bifurcated paths.',
                'background' : 'images/bosqueBif.jpg',
                'imagemap' : 'images/bosqueBif_map.jpg',
                'directions' : {
                   '1' : 'Waterfall',
                   '2' : 'Forest',
                   '3' : 'ForestZZ'
                  },
                'from' : {
                    'Waterfall' : [393, 495, Dir.E],
                    'Forest' : [1296, 747, Dir.W],
                    'ForestZZ' : [740, 1000, Dir.N]
                    },
                'waypoints' : [(397, 402)],
                'exitpoints' : {
                    '1' : (110,193),
                    '2' : (643,325),
                    '3' : (321,500)
                    },
                'music' : 'sounds/grillos.ogg',
                'items' : {
                   'feather' : {
                       'image' : 'images/feather.png',
                       'desc' : 'A nice looking feather. I\'m sure the bird does not need it anymore.',
                       'roomdesc' : 'a feather',
                       'visible' : True,
                       'mixwith' : {
                           'otheritem' : 'ink',
                           'summon' : 'pen'
                           },
                       'takeable' : True
                    }
                  }
                },                
            'Mill' : {
                'desc' : 'This area of the country has a water mill and a sign.',
                'background' : 'images/molino-agua.jpg',
                'imagemap' : 'images/molino-agua_map.jpg',
                'layers' : {
                    'mill-bridge' : {
                        'z' : 1006,
                        'xfrom' : 0,
                        'xto' : 430,
                        'layerimage' : 'images/mill-bridge.png'
                        },
                    'mill-sign' : {
                        'z' : 1080,
                        'xfrom' : 1659,
                        'xto' : 1915,
                        'layerimage' : 'images/mill-sign.png'
                        }
                    },
                'directions' : {
                   '1' : 'ForestZZ',
                   '2' : 'Deck'
                  },
                'from' : {
                    'ForestZZ' : [80, 950, Dir.E],
                    'Deck' : [1815, 995, Dir.W]
                    },
                'exitpoints' : {
                    '1' : (5,455),
                    '2' : (848,474)
                    },
                'music' : 'sounds/grillos.ogg',
                'items' : {
                   'sign' : {
                       'image' : 'images/xxx.png',
                       'desc' : 'a sign that explains how to escape the forest by going left, take another left, go up the cliff, and down the hill, and the rest was erased by some funny guy. Maybe you can write your own path...',
                       'roomdesc' : 'a wooden sign',
                       'visible' : True,
                       'takeable' : False
                    },
                   'ink' : {
                       'image' : 'images/ink.png',
                       'desc' : 'A full jar of strange ink. It may seem black but when you look at it closely, it has an uncommon glow.',
                       'roomdesc' : 'ink',
                       'visible' : True,
                       'mixwith' : {
                           'otheritem' : 'feather',
                           'summon' : 'pen'
                           },
                       'takeable' : True
                    }
                  }
                },
            'Deck' : {
                'desc' : 'From here, you can enter the forest from the beach.',
                'background' : 'images/beach-forest.jpg',
                'imagemap' : 'images/beach-forest_map.jpg',
                'layers' : {
                    'beach-bench' : {
                        'z' : 1000,
                        'xfrom' : 228,
                        'xto' : 747,
                        'layerimage' : 'images/beach-bench.png'
                        }
                    },
                'directions' : {
                   '1' : 'Beach',
                   '2' : 'Mill'
                  },
                'from' : {
                    'Beach' : [1434, 667, Dir.S],
                    'Mill' : [1065, 1017, Dir.N]
                    },
                'waypoints' : [(565, 447)],
                'exitpoints' : {
                    '1' : (639,284),
                    '2' : (430,504)
                    },
                'music' : 'sounds/seawaves.ogg',
                'items' : {
                   'deck' : {
                       'image' : 'images/xxx.png',
                       'desc' : 'a deck that connects the beach with the forest. You can walk on it.',
                       'roomdesc' : 'a wooden deck',
                       'visible' : True,
                       'takeable' : False
                    },
                   'bench' : {
                       'image' : 'images/xxx.png',
                       'desc' : 'a not-so-confy wooden bench. And no, you can\'t sit there.',
                       'roomdesc' : 'a wooden bench',
                       'visible' : True,
                       'takeable' : False
                    },
                   'paper' : {
                       'image' : 'images/paper.png',
                       'desc' : 'A full jar of strange ink. It may seem black but when you look at it closely, it has an uncommon glow.',
                       'roomdesc' : 'a piece of paper left on the floor',
                       'visible' : True,
                       'mixwith' : {
                           'otheritem' : 'sand',
                           'summon' : 'papyrus'
                           },
                       'takeable' : True
                    }
                  }
                },
            'Waterfall' : {
                'desc' : 'An extremelly beautiful waterfall crossed by a bridge.',
                'background' : 'images/waterfall-bridge.jpg',
                'imagemap' : 'images/waterfall-bridge_map.jpg',
                'blockages' : {
                    '1' : {
                        'active' : True,
                        'blockimage' : 'images/bridge-blockage.png',
                        }
                    },
                'directions' : {
                   '1' : 'ForestBif',
                   '2' : 'End'
                  },
                'from' : {
                    'End' : [730, 542, Dir.E],
                    'ForestBif' : [1162, 542, Dir.W]
                    },
                'exitpoints' : {
                    '1' : (541,250),
                    '2' : (309,250)
                    },
                'music' : 'sounds/waterfall.ogg',
                'items' : {
                   'bridge' : {
                       'image' : 'images/xxx.png',
                       'desc' : 'a bridge that leads outside the forest.',
                       'roomdesc' : 'a bridge',
                       'visible' : True,
                       'takeable' : False
                    },
                   'blockage' : {
                       'image' : 'images/xxx.png',
                       'desc' : 'some magical blockage over the bridge. You cannot pass through it.',
                       'roomdesc' : 'a blockage',
                       'visible' : True,
                       'blockid' : '1',
                       'blocked' : True,
                       'unlockeritem' : 'spell',
                       'unlockingtext' : 'You have cast a magical key spell and disolved the blockage!',
                       'takeable' : False
                    }
                  }
                },
            'End' : {
                'desc' : 'You have finally arrived to the end of this game. Hope to see you again in the next one.',
                'background' : 'images/grass-bottle.jpg',
                'imagemap' : 'images/grass-bottle_map.jpg',
                'layers' : {
                    'bottle-tree' : {
                        'z' : 616,
                        'xfrom' : 303,
                        'xto' : 608,
                        'layerimage' : 'images/bottle-tree.png'
                        }
                    },
                'directions' : {
                   '0346' : 'Nowhere'
                  },
                'from' : {
                    'Waterfall' : [1382, 648, Dir.W]
                    },
                'music' : 'sounds/magical.ogg',
                'items' : {            
                  }
                }

            }

    def setItems(self):
        # start with nothing on you
        self.inventory = {}

        # dictionary of items that will be available later on
        self.ghostitems = {
                'bayonet' : {
                    'image' : 'images/bayonet.png',
                    'roomdesc' : 'a bayonet',
                    'desc' : 'A handy although not that sharp custom bayonet',
                    'descwords' : ['spear','bayonet'],
                    'summonmessage' : 'Clever! You have made a bayonet out of a stick and that rusty knife.',
                    'visible' : True,
                    'takeable' : False
                },
                'papyrus' : {
                    'image' : 'images/papyrus.png',
                    'roomdesc' : 'a piece of papyrus',
                    'desc' : 'An oldish handmade papyrus. It almost seem real.',
                    'descwords' : ['papyrus'],
                    'summonmessage' : 'Who would have thought it... you have made a papyrus out of sand and a piece of paper.',
                    'visible' : True,
                    'mixwith' : {
                       'otheritem' : 'pen',
                       'summon' : 'script'
                       },
                    'takeable' : False
                },
                'pen' : {
                    'image' : 'images/pen.png',
                    'roomdesc' : 'a pen',
                    'desc' : 'A pen with strange ink, ready to be used.',
                    'descwords' : ['pen'],
                    'summonmessage' : 'Yes, you now can use the feather as a pen and write with that curious ink.',
                    'visible' : True,
                    'mixwith' : {
                       'otheritem' : 'papyrus',
                       'summon' : 'script'
                       },
                    'takeable' : False
                },
                'script' : {
                    'image' : 'images/script.png',
                    'roomdesc' : 'a script',
                    'desc' : 'A very unintelligible script.',
                    'descwords' : ['script'],
                    'summonmessage' : 'As you were writing, your mind went to dark places. I think that ink took control of your hand for a while...',
                    'visible' : True,
                    'mixwith' : {
                       'otheritem' : 'key',
                       'summon' : 'spell'
                       },
                    'takeable' : False
                },
                'spell' : {
                    'image' : 'images/spell.png',
                    'roomdesc' : 'a spell',
                    'desc' : 'An "Open Spell" summoned all by yourself. Yeah!',
                    'descwords' : ['spell'],
                    'summonmessage' : 'Holding the key with one hand, and reading the script outloud (don\'t worry, nobody\'s watching), created a magical spell.',
                    'visible' : True,
                    'takeable' : False
                },
            }

    def gameLoop(self):
        while self.run: # Game Loop
            dt = self.clock.tick(self.FPS) / 1000 # Returns milliseconds between each call to 'tick'. The convert time to seconds.
            #pygame.time.delay(100)
            self.dirtyscreen = False
            events = pygame.event.get() # para el textInput
            
            for event in events:
                if (event.type == pygame.QUIT):
                    self.run = False
                if (event.type == pygame.KEYUP):
                    if (event.key == pygame.K_ESCAPE):
                        events.remove(event) # no imprimo este caracter
                        self.run = False
                    if (event.key == pygame.K_TAB):
                        self.show_inventory = False
                        self.dirtyscreen = True
                        events.remove(event) # no imprimo este caracter
                    if (event.key == pygame.K_F1):
                        self.showHelp()
                    if (event.key == pygame.K_F3):
                        largo = len(self.previoustext)
                        if (largo > 0):
                            self.textinput.input_string = self.previoustext # repetir el ultimo comando
                            self.textinput.cursor_position = largo
                if (event.type == pygame.KEYDOWN):
                    if (event.key == pygame.K_ESCAPE):
                        events.remove(event) # no imprimo este caracter
                        self.run = False
                    if (event.key == pygame.K_TAB):
                        self.show_inventory = True
                        self.dirtyscreen = True
                        events.remove(event) # no imprimo este caracter
                #elif event.type == pygame.MOUSEMOTION:
                    # Left mouse button:       1
                    # Mouse wheel button:      2
                    # Right mouse button:      3
                    # Mouse wheel scroll up:   4
                    # Mouse wheel scroll down: 5
                    # 'rel' is a tuple (x, y). rel[0] is the x-value. rel[1] is the y-value.
                    #log('DEBUG','Mouse move:','dx='+str(event.rel[0]),'dy='+str(event.rel[1]),'x='+str(event.pos[0]),'y='+str(event.pos[1]))
                    #if event.rel[0] > 0: # 'rel' is a tuple (x, y). 'rel[0]' is the x-value.
                    #    log('DEBUG',"You're moving the mouse to the right")
                    #elif event.rel[1] > 0: # pygame start y=0 at the top of the display, so higher yvalues are further down.
                    #    log('DEBUG',"You're moving the mouse down")
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:
                        log('DEBUG',"Left mouse button DOWN",'x='+str(event.pos[0]),'y='+str(event.pos[1]))
                    elif event.button == 3:
                        log('DEBUG',"Right mouse button DOWN",'x='+str(event.pos[0]),'y='+str(event.pos[1]))
                elif event.type == pygame.MOUSEBUTTONUP:
                    if event.button == 1:
                        log('INFO',"Left mouse button UP",'x='+str(event.pos[0]),'y='+str(event.pos[1]),'color='+str(self.getColor((event.pos[0],event.pos[1]))))
                        posfrom = self.player.getFootXY()
                        waypoints = self.findWaypoints(posfrom,(event.pos[0],event.pos[1]))
                        self.player.walkTo(waypoints)
                    elif event.button == 3:
                        log('DEBUG',"Right mouse button UP",'x='+str(event.pos[0]),'y='+str(event.pos[1]))

            # Feed textInput with events every frame
            texto1 = self.textinput.get_text()
            if self.textinput.update(events): # capturar texto con ENTER
                texto = self.textinput.get_text()
                #texto = filter_nonprintable(texto)
                if len(texto)>0:
                    self.textinput.clear_text()
                    # Procesar comando ingresado
                    self.previoustext = texto
                    self.procesarComando(texto)
            
            texto2 = self.textinput.get_text()
            if texto1 != texto2:
                self.dirtyscreen = True
            
            player_moved = False
            if self.keys_allowed:
                keys = pygame.key.get_pressed()
                player_moved = self.player.update(keys, dt) # actualizo el sprite jugador segun las teclas
                if player_moved:
                    self.dirtyscreen = True

            if self.show_message:
                self.dirtyscreen = True
            self.updateMessage()
            
            if self.dirtyscreen: # intentar no refrecar todo el tiempo si no es necesario
                self.draw_screen()

        self.doQuit()

    def saveGame(self, file='default.json'):
        # Guardar: room actual, coordenadas foot del player, inventory, ghostinv....
        # ¿como hacer para guardar estado de los items del room? Por ahora, guardo rooms completo.
        # armo un JSON state que contenga los demas elementos
        state = {}
        state['inventory'] = self.inventory
        state['rooms'] = self.rooms
        state['ghostinv'] = self.ghostitems
        state['player'] = self.player.saveState()
        state['currentRoom'] = self.currentRoom
        #print(state) # impresion de Python
        log('DEBUG',json.dumps(state)) # impresion de modulo json
        if False:
            with open(file, 'w') as outfile:
                json.dump(state, outfile)
        else:
            compressed_pickle(file, state)
            
    def loadGame(self, file='default.json'):
        log('DEBUG', 'load')
        try:
            if False:
                with open(file) as json_file:
                    state = json.load(json_file)
            else:
                state = decompress_pickle(file)
            log('DEBUG',state)
            self.inventory = state['inventory']
            self.rooms = state['rooms']
            self.ghostitems = state['ghostinv']
            playerstate = state['player']
            room = state['currentRoom']
            self.goToRoom(room)        
            self.player.loadState(playerstate)
            return True
        except IOError:
            return False
    
def log(level, *arg):
    # log_level:
    #   NONE:  no escribir nada
    #   INFO:  solo infotmativos
    #   DEBUG: mas informacion para debugear
    if log_level != 'NONE':
        if (level == 'INFO') or (log_level == 'DEBUG' and level == 'DEBUG'):
            print(arg)
    
def loadImage(imagepath, scale_width=0, scale_height=0):
    # Uso el dictionary cached_images para almacenar filenames en key y pixels de imagen en value.
    # Reemplazo las llamadas a pygame.image.load()
    # OJO: os.path.join('images','pepe.png') se puede usar para migrar a otro S.O.
    # J P G => S L D
    # P N G => T R N
    # M P 3 => S N D
    if imagepath in cached_images.keys():
        image = cached_images[imagepath]
        #print ('loadImage: hit cache')
    else:
        imagepath_ok = normalizePath(imagepath)
        image = pygame.image.load(imagepath_ok)
        # Si quiero escalar
        if scale_width > 0:
            image = pygame.transform.scale(image, (scale_width, scale_height)) # devuelve Surface
        #image = image.convert_alpha() # TEST
        cached_images[imagepath] = image
        #print ('loadImage: read ' + imagepath + ' from disk')
    return image

def loadSound(soundpath):
    if soundpath in cached_sounds.keys():
        sound = cached_sounds[soundpath]
    else:
        #musica.load(soundpath)
        cached_sounds[soundpath] = sound
    return sound

def normalizePath(input_path):
    parts = input_path.split('/')
    path = parts[0]
    file = parts[1]
    path_ok = os.path.join(path, file) # Independiente del S.O.
    return path_ok

def getGreenColor(color):
    G = color[1]
    return G

def getBlueColor(color):
    B = color[2]
    return B
    
def Ceil(number): # reemplazo de math.ceil()
    #return int(-1 * number // 1 * -1)
    res = int(number)
    return res if res == number or number < 0 else res+1

def CeilDivision(number1, number2):
    # OJO: math.ceil() Returns an int value in Python 3+, while it returns a float in Python 2.
    # -(-3//2) da 2
    return -(-number1 // number2)

def sign(number):
    if number < 0:
        return -1
    else:
        return 1

def relStepXY(step, dxy):
    # En funcion de las coordenadas delta XY, calculo cuanto del step le corresponde
    # al eje X y cuanto al eje Y usando trigonometria y proporcionalidad en triangulos
    dx = dxy[0]
    dy = dxy[1]
    signx = sign(dx)
    signy = sign(dy)
    if dx == 0: # prevenir division por cero
        rel = dy # ¿esta bien esto?
    else:
        rel = dy / dx
    rel2 = rel**2 # rel al cuadrado
    step2 = step**2
    aux = 1 / (rel2 + 1)
    stepx = signx * step * math.sqrt(aux)
    stepy = signy * step * math.sqrt(1 - aux)
    stepXY = (stepx, stepy)
    return stepXY

def deltaXY(xyFrom, xyTo):
    dx = xyTo[0] - xyFrom[0] # delta X
    dy = xyTo[1] - xyFrom[1] # delta Y
    return (dx, dy)

def lengthXY(xyFrom, xyTo):
    dxy = deltaXY(xyFrom, xyTo)
    dist = math.sqrt(dxy[0]**2 + dxy[1]**2)
    return dist

def closestTo(coordlist, xyTo):
    # devuelvo, de la lista, la coordenada mas cercana a xyTo
    cant = len(coordlist)
    if cant == 1:
        return coordlist[0]
    else:
        closest = 0
        min_dist = 999999
        for i in range(cant):
            coord = coordlist[i]
            dist = lengthXY(coord, xyTo)
            if dist < min_dist:
                min_dist = dist
                closest = i
        return coordlist[closest]

def orderedCoordsTo(coordlist, xyTo):
    # devuelvo la lista de coordenadas segun cercania a xyTo
    cant = len(coordlist)
    if cant == 1:
        return coordlist
    else:
        dists = []
        ordered_coordlist = []
        # calcular distancias desde cada coordenada hasta xyTo, e incluirlas en un vector
        for i in range(cant):
            coord = coordlist[i]
            dist = lengthXY(coord, xyTo)
            tupla = (i,dist)
            dists.append(tupla)
        # ordenar la lista de distancias
        ordered_dists = bubbleTupleSort(dists)
        # reordenar la lista de coordenadas segun sus distancias
        for i in range(cant):
            ordered_coordlist.append( coordlist[ordered_dists[i][0]] )
        return ordered_coordlist

def bubbleTupleSort( tuples ):
    # BubbbleSort de tuplas, donde el primer valor es el indice, y el segundo
    # es el "peso" (en este caso la distancia). Debo comparar con tuples[x][1]
    n = len( tuples )
    log('DEBUG','bubblesort tuples IN:',tuples)
    for i in range( n - 1 ) :
        flag = 0
        for j in range(n - 1) :
            log('DEBUG','tupla '+str(j),tuples[j])
            if tuples[j][1] > tuples[j + 1][1] : # comparo por "peso"
                tmp = tuples[j]
                tuples[j] = tuples[j + 1]
                tuples[j + 1] = tmp
                flag = 1
        if flag == 0:
            break
    log('DEBUG','bubblesort tuples OUT:',tuples)
    return tuples

# EJ: print (rndStrMemory(['uno','dos','tres','cuatro']))
def randomString(stringList):
    selected = random.choice(stringList)
    return selected

def rndStrMemory(stringList):
    global memoryList # dictionary cache de todas las listas de textos. Uso el hash como key
    key = hash(str(stringList))
    if key in memoryList:
        # si existe, obtego la ultima lista recortada
        shortList = memoryList[key]
        if len(shortList) == 0: # si ya esta vacia la lista, reiniciarla
            shortList = stringList
    else:
        memoryList[key] = stringList # si no existia, la agrego
        shortList = stringList
    # selecciono una opcion de la lista actual
    selected = randomString(shortList)
    # recorto la lista para la proxima
    shortList.remove(selected)
    # actualizo la lista en el dictionary cacheado
    memoryList[key] = shortList
    return selected

def filter_nonprintable(texto):
    log('DEBUG','antes  : '+texto)
    #textof = filter(lambda x: x in string.printable, texto) # filtrar caracteres no imprimibles
    textof = ''.join(c for c in texto if not unicodedata.category(c).startswith('C'))
    log('DEBUG','despues: '+textof)
    return textof

# Pickle a file and then compress it into a file with extension 
def compressed_pickle(file, data):
    ext = '.pbz2'
    with bz2.BZ2File(file + ext, 'w') as f: 
        cPickle.dump(data, f)

# Load any compressed pickle file
def decompress_pickle(file):
    ext = '.pbz2'
    data = bz2.BZ2File(file + ext, 'rb')
    data = cPickle.load(data)
    return data

def main():  # type: () -> None
    global log_level
    global screenrel
    global memoryList

    log_level = 'NONE' # NONE , INFO , DEBUG
    screenrel = 1.5 # relacion entre tamaño de pantalla y tamaño de ventana
    memoryList = {}

    successes, failures = pygame.init() # starts with a hidden window
    # Inicializar PyGame y pantalla
    log('DEBUG','PyGame Init', 'Successes: '+str(successes), 'Failures: '+str(failures))
    screenw = pygame.display.Info().current_w
    screenh = pygame.display.Info().current_h
    width = int(screenw / screenrel)
    height = int(screenh / screenrel)
    # posicionar la ventana centrada
    xc = ( pygame.display.Info().current_w - width ) / 2
    yc = ( pygame.display.Info().current_h - height ) / 2
    log('DEBUG','Center window','x:'+str(xc),'y:'+str(yc))
    os.environ['SDL_VIDEO_WINDOW_POS'] = "%d,%d" % (xc,yc) 
    # los doble parentesis son "2-item sequence"
    log('INFO','Setting display mode','window:',(width, height),'screen:',(screenw,screenh))
    screen = pygame.display.set_mode((width, height)) # the screen is a Surface!
    # Para no tener variables globales, se crea un objeto de una clase, que puede
    # pasarse como parametro, y usar los metodos de la clase para acceder a sus variables.
    Game().main(screen)
    # En vez de Game() podria haber varios Level(), cada uno con un "tipo" de nivel
    # diferente, que trate los eventos de su game loop de manera distinta; y podrìan incluso
    # llamarse unos a otros.
    pygame.quit
    quit()

if __name__ == "__main__":
    main()
