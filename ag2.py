# Autor: Alejandro Biasin, 2020
# AG2 es un upgrade de AG1. Nuevos features:
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
        self.move_step = 5
        
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
        return screenmap.get_at( (x, y) )

    def getGreenColor(self, color):
        G = color[1]
        return G
    
    def getBlueColor(self, color):
        B = color[2]
        return B
        
    def getScaleByColor(self, color):
        minscale = 0.1 # para que al menos siempre sea visible
        errorscale = 0.01 # si es menor a esto, hay algo raro!
        scale = self.getBlueColor(color) / 200 # escala del sprite segun tono de azul del mapa
        if scale < minscale:
            if scale < errorscale:
                scale = 0
                log('DEBUG','error scale! ',scale, ' con color ',color)
            else:
                log('DEBUG','minscale! ',scale, ' con color ',color)
                scale = minscale
        return scale
    
    def isPositionAllowed(self, color):
        B = self.getBlueColor(color)
        if B == 0: # B=0 es una posicion prohibida, no debiera llegar aca!
            return False
        if self.isPositionBlocked(color):
            return False # blocking object active, cant pass throught!
        return True


    def isPositionBlocked(self, color):
        G = self.getGreenColor(color)
        if (G > 100) and (G < 200): 
            blockid = (G - 100) // 10 # decena del color verde
            log('DEBUG','block id: ',blockid)
            if rooms[currentRoom]['blockages'][str(blockid)]['active'] == True:
                return True
        return False

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

    def changingRoomTo(self, x, y):
        color = self.getColor(x, y)
        G = self.getGreenColor(color)
        # G = 200 + room_number * 10 + descarte (tomo la decena)
        if (G == 0) or (G < 200): 
            return 0 # no cambia de room
        room = (G - 200) // 10
        return room

    def setRectByFootAndScale(self):
        # obtengo el color (R,G,B) en el mapa
        colorxy = self.getColor()
        if self.isPositionAllowed(colorxy):
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
        log('DEBUG','rect moved to ',x,y)

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

    def scaleImage(self):
        cur_width = self.image.get_width()
        cur_height = self.image.get_height()
        new_width = Ceil(cur_width * self.scale)
        new_height = Ceil(cur_height * self.scale)
        dx = cur_width - new_width
        dy = cur_height - new_height
        if (dx != 0 or dy != 0):
            log('DEBUG','scaled by ' , self.scale)
            self.image = pygame.transform.scale(self.image, (new_width, new_height))        
        
    def update(self, keys):
        has_moved = False
        if 1 in keys: # si hay alguna tecla presionada
            new_x = self.xfoot
            new_y = self.yfoot
            direction = Dir.none
            if keys[pygame.K_LEFT] and not keys[pygame.K_RIGHT]:
                new_x -= self.move_step
                has_moved = True
                direction = Dir.W
            if keys[pygame.K_RIGHT] and not keys[pygame.K_LEFT]:
                new_x += self.move_step
                has_moved = True
                direction = Dir.E
            if keys[pygame.K_UP] and not keys[pygame.K_DOWN]:
                new_y -= self.move_step
                has_moved = True
                #if direction == Dir.none:
                direction = Dir.N
                #elif direction == Dir.E:
                #    direction = Dir.NE
                #elif direction == Dir.W:
                #    direction = Dir.NW
            if keys[pygame.K_DOWN] and not keys[pygame.K_UP]:
                new_y += self.move_step
                has_moved = True
                #if direction == Dir.none:
                direction = Dir.S
                #elif direction == Dir.E:
                #    direction = Dir.SE
                #elif direction == Dir.W:
                #    direction = Dir.SW
                
            if has_moved:
                if self.insideScreen(new_x, new_y):
                    room = self.changingRoomTo(new_x, new_y)
                    if room > 0:
                        # convertir el numero de salida del mapa grafico a un Room
                        newRoom = rooms[currentRoom]['directions'][str(room)]
                        self.game.goToRoom(newRoom) # Interaccion entre clase Sprite y clase Game
                    elif self.canMove(new_x, new_y):
                        self.direction = direction
                        self.cycleImage()                
                        self.moveFeetTo(new_x, new_y)
                        self.setRectByFootAndScale()
                    log('DEBUG',self.direction)
                else:
                    has_moved = False
        return has_moved

    def cycleImage(self):
        # if self.direction == Dir.E ...
        self.index += 1
        if self.index >= len(self.images[int(self.direction.value)]):
            self.index = 0        
        #self.image = self.images[self.direction.value][self.index]
        self.updateImage()
    
    def updateImage(self):
        # actualiza la imagen actual en base a la direccion y el index
        self.image = self.images[int(self.direction)][self.index]
        
    def insideScreen(self, x, y):
        if x <= 0:
            return False
        if x >= width:
            return False
        if y <= 0:
            return False
        if y >= height:
            return False
        return True
        
    def canMove(self, x, y):
        # no permitir si sale de la pantalla
        if self.insideScreen(x, y) == False:
            return False
        # no permitir si ingresa a una zona del mapa no permitida (en negro)
        colorxy = self.getColor(x, y)
        if self.isPositionAllowed(colorxy) == False:
            return False        
        return True
    
def main():  # type: () -> None
    global log_level
    global screenrel

    log_level = 'NONE' # NONE , INFO , DEBUG

    pygame.init() # starts with a hidden window
    # Inicializar PyGame y pantalla
    log('DEBUG','Init')
#    pygame.init()
    screenrel = 1.5
    width = int(pygame.display.Info().current_w / screenrel)
    height = int(pygame.display.Info().current_h / screenrel)
    # posicionar la ventana centrada
    log('DEBUG','Center window')
    xc = ( pygame.display.Info().current_w - width ) / 2
    yc = ( pygame.display.Info().current_h - height ) / 2
    os.environ['SDL_VIDEO_WINDOW_POS'] = "%d,%d" % (xc,yc) 
    # los doble parentesis son "2-item sequence"
    log('DEBUG','Setting display mode')
    screen = pygame.display.set_mode((width, height)) # the screen is a Surface!
    log('INFO','Initial size: ',(width, height))
    # Para no tener variables globales, se crea un objeto de una clase, que puede
    # pasarse como parametro, y usar los metodos de la clase para acceder a sus variables.
    Game().main(screen)
    # En vez de Game() podria haber varios Level(), cada uno con un "tipo" de nivel
    # diferente, que trate los eventos de su game loop de manera distinta; y podrìan incluso
    # llamarse unos a otros.
    pygame.quit
    quit()

def log(level, *arg):
    # log_level:
    #   NONE:  no escribir nada
    #   INFO:  solo infotmativos
    #   DEBUG: mas informacion para debugear
    if log_level != 'NONE':
        if (level == 'INFO') or (log_level == 'DEBUG' and level == 'DEBUG'):
            print(arg)
    
class Game(object):
    def main(self, screen):
        # Variables globales
        global width
        global height
        global clock
        global FPS
        global inventory
        global show_inventory
        global rooms
        global currentRoom
        global musica
        global global_text
        global show_message
        global message_time
        global previoustext
        global maxstringlength
        global smallfont
        global textcolor
        global cursorcolor
        global backtextcolor
        global backinvcolor
        global backitemcolor
        global fontsize
        global run
        global textinput
        global textX
        global textY
        global textinputX
        global textinputY
        #global text # TODO: Quitar
        global player
        global sprites
        global keys_allowed
        global cached_images
        global cached_sounds
        global dirtyscreen
    #    global log_level
        global has_audio

        self.screen = screen
    #    log_level = 'NONE' # NONE , INFO , DEBUG
        # En pygame:
        #  - se usa Surface para representar la "apariencia", y
        #  - se usa Rect para representar la posicion, de un objeto.
        #  - se hereda de pygame.sprite.Sprite para crear sprites, y con Group se los agrupa.

        width = screen.get_width()
        height = screen.get_height()
        
        gamename = 'Alex\'s First Graphic Adventure Game, with a twist'
        log('DEBUG','Setting caption')
        pygame.display.set_caption(gamename)
        cached_images = {}
        dirtyscreen = True
        # en vez de pygame.time.delay(100), usar clock para controlar los FPS
        log('DEBUG','Init clock and FPS')
        clock = pygame.time.Clock()
        FPS = 15 # Frames per second.
        # Message Box
        global_text = ''
        show_message = False
        message_time = 0
        previoustext = ''    
        # defining a font 
        #fontsize = int(40 / screenrel) # para default/none
        fontsize = int(28 / screenrel) # para Arial
        maxstringlength = 50
        pygame.font.init()
        #defaultfont =  pygame.font.get_default_font()
        #customfont = defaultfont # 'Corbel'
        #customfont = None
        customfont = 'Arial'
        log('DEBUG','Setting small Font')
        smallfont = pygame.font.SysFont(customfont, fontsize)
        #smallfont = pygame.font.Font(customfont, fontsize)
        log('DEBUG','Setting colors')
        textcolor = (255, 220, 187) # RGB default textcolor
        cursorcolor = (187, 220, 255)
        backtextcolor = (170, 170, 170, 190) # fondo translucido de texto
        backinvcolor = (87, 27, 71, 150) # fondo translucido de inventario
        backitemcolor = (142, 67, 192, 190) # fondo translucido de inventario
        textX = width/3
        textY = height/3
        textinputX = 10
        textinputY = height-fontsize-13
        show_inventory = False
        currentRoom = ''
        run = True
        # Create TextInput-object (3rd party library)
        log('DEBUG','Init textinput')
        textinput = pygame_textinput.TextInput(text_color = textcolor, cursor_color = cursorcolor, font_family = customfont, font_size = fontsize, max_string_length = maxstringlength)
        
        log('DEBUG','Setting rooms and items')
        self.setRooms()
        self.setItems()
        
        # Cargar sonido
        #grillos = pygame.mixer.Sound('grillos.wav')
        log('DEBUG','Init sounds')
        try:
            pygame.mixer.init()
            musica = pygame.mixer.music
            has_audio = True
        except Exception as err:
            log('INFO','Error: No audio device')
            has_audio = False
            
        # Setup the player sprite and group
        player = Player(self)
        sprites = pygame.sprite.Group(player)
        # start the player in the first room
        self.goToRoom('Forest') # Primer room de la lista    
        # draw the initial screen
        self.draw_screen()
        keys_allowed = True
        
        # and let the game begin
        self.gameLoop()

    def doQuit(self):
        # Desactivar sonido y video, y salir
        self.globalMessage(randomString(['Bye bye!','We\'ll miss you...','Don\'t be frustrated. You\'ll make it next time.']))
        self.draw_screen()
        sleep(1)
        if has_audio:
            musica.stop()
        pygame.quit()
        quit()

    def drawText(self, texto, color, x, y):
        textosurf = smallfont.render(texto , True , color)
        self.screen.blit(textosurf, (x, y) )
            
    def globalMessage(self,texto):
        global global_text
        global show_message
        global message_time
        global dirtyscreen
        #global_text = filter_nonprintable(texto)
        global_text = texto
        show_message = True
        dirtyscreen = True
        message_time = int(2 + math.sqrt(len(global_text)) * (FPS/2)) # tiempo en pantala proporcional al texto

    def updateMessage(self):
        global show_message
        global message_time
        message_time -= 1
        if message_time == 0:
            show_message = False # si la cuenta regresiva termino, quitar mensaje

    def drawMessage(self):
        ancho_recuadro = 40 # en caracteres
        aspectw = int(14 / screenrel)
        # TODO: Arreglar ancho cuando hay 2 renglones desproporcionados
        wrappedlines = textwrap.wrap(global_text, ancho_recuadro, replace_whitespace=False)
        lineas_recuadro = len(wrappedlines)
        dw = 5 # delta/margen de ancho
        dh = 5 # delta/margen de alto
        maxlen = 0
        for line in wrappedlines: # obtengo ancho maximo
            if len(line) > maxlen:
                maxlen = len(line)
        #w = (len(global_text)*aspectw + dw) / lineas_recuadro # ancho de la caja de texto (teniendo en cuenta wrap)
        w = int(maxlen * aspectw) + dw
        fh = fontsize + dh + 4 # alto de una linea de texto
        h = fh * lineas_recuadro # altura total del recuadro (teniendo en cuenta wrap)
        x = width/2 - w/2
        y = height/2 - h/2
        self.drawRect(x,y,w,h,backtextcolor) # recuadro de fondo
        i = 0
        for line in wrappedlines:
            self.drawText(line, textcolor, x+dw, y+dh+i*fh)
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
            self.loadGame()
            self.globalMessage('Game loaded')
        #some fun
        elif words[0] == 'jump':
            self.globalMessage(randomString(['There is no jumping in this game','This is Kaos. We don\'t jump here!']))
        elif words[0] == 'dive':
            self.globalMessage(randomString(['Are you nuts?','You should change your pills.','No diving in this area!']))
        elif words[0] == 'sit':
            self.globalMessage(randomString(['There is no time to be wasting.','Walking is good for your health.','Nah, I don\'t wan\'t to sit, thanks.']))
        elif words[0] == 'sleep':
            self.globalMessage(randomString(['Come on you lazy cow!','There is no time for a nap','No! Wake up!']))
        elif words[0] in ('talk','scream','shout'):
            self.globalMessage(randomString(['Shhh!']))
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
            self.comandoGoRoom(words[1])
        elif (words[0] == 'use') and (len(words)>3) and (words[2] == 'with'):
            self.comandoUse(words[1], words[3])
        else:
            self.globalMessage(randomString(['Incorrect command','Not sure what you mean','Try something else']))

    def showHelp(self):
    #2345678901234567890123456789012345678901234567890123456789012345678901234567890
        helpmessage = """               -< Command Help >-                                        
        look : describes what's around you.                                             
        look [item] : describes an item in your inventory or in the room.               
        get [item] : takes an object of the room and keeps it in your inventory.        
        use [item] with [item] : tries to make an interaction between the two items.    
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
            self.globalMessage(randomString(['You can\'t go that way!','Really? '+direction+'?','Consider getting a compass','I don\'t think going that way is the right way','Danger! Going that way is demential (because it doesn\'t exists)']))

    def comandoLookRoom(self):
        # mostrar descripcion del room actual, y posibles salidas
        mensaje = rooms[currentRoom]['desc']
        # mostrar los items que hay en el room actual
        if bool(rooms[currentRoom]['items']):
            mensaje += ' You see '
            i = 0
            cantitems = len(list(rooms[currentRoom]['items']))
            for item in rooms[currentRoom]['items']:
                i += 1
                if (rooms[currentRoom]['items'][item]['visible'] == True):
                    if i > 1:
                        mensaje += ', '
                        if cantitems == i:
                            mensaje += 'and '
                    mensaje += rooms[currentRoom]['items'][item]['roomdesc']
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
        if (itemstr in inventory.keys()): # si el item lo tengo yo
            mensaje = inventory[itemstr]['desc']
        else:
            if (itemstr in rooms[currentRoom]['items'].keys()): # si el item esta en el room
                if (rooms[currentRoom]['items'][itemstr]['takeable'] == True):
                    mensaje = 'You see ' + rooms[currentRoom]['items'][itemstr]['roomdesc']
                else:
                    if rooms[currentRoom]['items'][itemstr]['visible'] == True:
                        if ('locked' in rooms[currentRoom]['items'][itemstr]) and (rooms[currentRoom]['items'][itemstr]['locked'] == False) and (rooms[currentRoom]['items'][itemstr]['iteminside'] in rooms[currentRoom]['items'].keys()):
                            mensaje = 'You see ' + rooms[currentRoom]['items'][itemstr]['roomdescunlocked']
                        else:
                            mensaje = 'You see ' + rooms[currentRoom]['items'][itemstr]['desc']
                    else:
                        mensaje = randomString(['I don\'t see any ' + itemstr, 'It may have dissapeared, you know.','Are you sure the '+ itemstr +' is still there?'])
            else:
                if (itemstr in rooms[currentRoom]['directions'].keys()):
                    mensaje = 'Yes, you can go ' + itemstr
                else:
                    mensaje = randomString(['The ' + itemstr + ' is not here' , 'I don\'t see any ' + itemstr])
        self.globalMessage(mensaje)

    def comandoGetItem(self,itemstr):
        if (itemstr in inventory.keys()):
            mensaje = 'You already have the ' + itemstr
        else:
            if (itemstr in rooms[currentRoom]['items']) and (rooms[currentRoom]['items'][itemstr]['visible'] == True):
                if (rooms[currentRoom]['items'][itemstr]['takeable']):
                    #add the item to their inventory
                    inventory[itemstr] = rooms[currentRoom]['items'][itemstr]
                    #display a helpful message
                    mensaje = randomString([itemstr + ' got!','Yeah! You have gotten the '+itemstr,'The '+itemstr+', just what you\'ve been looking for','At last, the glorious '+itemstr ])
                    #delete the item from the room
                    del rooms[currentRoom]['items'][itemstr]
                else:
                    mensaje = randomString(['You can\'t get the ' + itemstr, 'Nah! It\'s like painted to the background', 'You wish!'])
            else:
                #tell them they can't get it
                mensaje = randomString([itemstr + ' is not here', 'Nah!', 'You wish!'])
        self.globalMessage(mensaje)
        
    def comandoUse(self,item1, item2):
        # item1 debe estar en el inventory
        # item2 puede estar en el room (para accionar algo) o en el inventory (para mezclarlos)
        if (item1 in inventory.keys()):
            if (item2 in inventory.keys()): # mezclar 2 items del inventory
                if ('mixwith' in inventory[item1]) and ('mixwith' in inventory[item2])==True and (inventory[item1]['mixwith']['otheritem'] == item2) and (inventory[item2]['mixwith']['otheritem'] == item1):
                    # creo el nuevo item
                    nuevoitem = inventory[item2]['mixwith']['summon']
                    inventory[nuevoitem] = ghostitems[nuevoitem]
                    # delete both original items from the inventory
                    del inventory[item1]
                    del inventory[item2]
                    del ghostitems[nuevoitem]
                    #display a helpful message
                    #globalMessage('summoned a ' + nuevoitem)
                    mensaje = inventory[nuevoitem]['summonmessage']
                else:
                    mensaje = randomString(['Can\'t use ' + item1 + ' with ' + item2 + '!','I don\'t think the '+item1+' is meant to be used with the '+item2,'...'+item1+' with '+item2+' does not compute.'])
            elif (item2 in rooms[currentRoom]['items']): # accionar algo que esta 'locked'
                if ('locked' in rooms[currentRoom]['items'][item2]):
                    if (rooms[currentRoom]['items'][item2]['locked'] == True):
                        if (item1 == rooms[currentRoom]['items'][item2]['unlockeritem']):
                            # al accionar item2 con item1, queda visible iteminside
                            rooms[currentRoom]['items'][item2]['locked'] = False # lo destrabo y queda asi
                            if ('iteminside' in rooms[currentRoom]['items'][item2]):
                                iteminside = rooms[currentRoom]['items'][item2]['iteminside']
                                rooms[currentRoom]['items'][iteminside]['visible'] = True # descubro el iteminside
                                mensaje = rooms[currentRoom]['items'][item2]['unlockingtext']
                            else:
                                mensaje = 'OJO: el iteminside no esta en '+currentRoom # no debiera llegar aca
                        else:
                            mensaje = 'I think the '+item1+' is not meant to be used with the '+item2+'.'
                    else:
                        mensaje = randomString(['Not again!','You\'ve already done that.','Don\'t be repetitive dude!'])
                elif ('blocked' in rooms[currentRoom]['items'][item2]): # destrabar algo para poder pasar
                    if (rooms[currentRoom]['items'][item2]['blocked'] == True):
                        if (item1 == rooms[currentRoom]['items'][item2]['unlockeritem']):
                            rooms[currentRoom]['items'][item2]['blocked'] = False # destrabo el bloqueo y queda asi
                            rooms[currentRoom]['items'][item2]['visible'] = False # ya no se ve el bloqueo
                            blockid = rooms[currentRoom]['items'][item2]['blockid'] # ID del blockage
                            rooms[currentRoom]['blockages'][blockid]['active'] = False # libero el bloqueo para que el player pueda pasar
                            mensaje = rooms[currentRoom]['items'][item2]['unlockingtext']
                        else:
                            mensaje = 'I think the '+item1+' is not meant to be used with the '+item2+'.'
                    else:
                        mensaje = randomString(['Are you still seeing that?','You\'ve already done that.','Don\'t be repetitive pal!'])
                else:
                    mensaje = randomString(['Can\'t use ' + item1 + ' with ' + item2 + '!','I don\'t think the '+item1+' is meant to be used with the '+item2,'...'+item1+' with '+item2+' does not compute.'])
            else:
                mensaje = randomString(['There is no ' + item2 + ' around.', 'Try something else.'])
        else:
            mensaje = 'You don\'t have any ' + item1
        self.globalMessage(mensaje)

    def loadMusic(self,musicpath):
        musicpath_ok = normalizePath(musicpath)
        if has_audio:
            musica.load(musicpath_ok)

    def goToRoom(self,newroom):
        global currentRoom
        global background
        #global textcolor
        global screenmap
    #    global player
        global keys_allowed
        global bckwrel
        global bckhrel
        keys_allowed = False
        # Cargar fondo en memoria y redimensionarlo para que ocupe la ventana
        backimage = rooms[newroom]['background']
        background = pygame.image.load(normalizePath(backimage))
        background = background.convert() # TEST
        bckw = background.get_width()
        bckh = background.get_height()
        bckwrel = bckw / width
        bckhrel = bckh / height
        log('INFO','background original size:', bckw, bckh, bckwrel, bckhrel, width, height)
        background = pygame.transform.scale(background, (width, height)) # devuelve Surface
        # Cargar el mapa de escalas correspondiente al fondo
        imagemap = rooms[newroom]['imagemap']
        screenmap = pygame.image.load(normalizePath(imagemap))
        screenmap = screenmap.convert()
        screenmap = pygame.transform.scale(screenmap, (width, height)) # devuelve Surface
        # Cargar musica de fondo del room
        tema = rooms[newroom]['music']
        #print ('yendo de ' + currentRoom + ' a ' + newroom + ' con tema ' + tema)
        #musica.load(tema)
        if has_audio:
            self.loadMusic(tema)
            musica.play(-1) # If the loops is -1 then the music will repeat indefinitely.
            
        # obtengo coordenadas y direction del player al ingresar a este room desde el anterior
        if (currentRoom in rooms[newroom]['from']): # si no existe es porque hice loadGame
            coords = rooms[newroom]['from'][currentRoom]    
            log('INFO','Yendo de ',currentRoom,' a ',newroom, coords)
            #textcolor = (34, 120, 87)
            # convertir coordenadas externas a internas
            x = self.relativeW(coords[0])
            y = self.relativeH(coords[1])
            player.setPosition(x, y, coords[2])
        currentRoom = newroom
        keys_allowed = True
        
    def relativeW(self,x):
        log('DEBUG','relativeW: ',x,bckwrel,int(x / bckwrel))
        return int(x / bckwrel)
        
    def relativeH(self,y):
        log('DEBUG','relativeH: ',y,bckhrel,int(y / bckhrel))
        return int(y / bckhrel)

    def drawRect(self,x,y,w,h,color):
        surf = pygame.Surface([w, h], pygame.SRCALPHA)
        surf.fill(color)
        self.screen.blit(surf, [x,y,w,h])

    def drawItem(self,x,y,w,h,itemimagefile):
        itemimage = loadImage(itemimagefile, int(w), int(h))
        self.screen.blit(itemimage, (x, y))

    def drawInventory(self):
        # si no tengo nada en el inventario, mostrar mensaje
        if bool(inventory) == False:
            self.globalMessage(randomString(['You are carrying nothing!', 'Nothing in your pockets so far', 'Maybe if you start using the "get" command...']))
        else:
            itemsperrow = 2 # max columns
            listaitems = list(inventory)
            cantitems = len(listaitems)
            rows = CeilDivision(cantitems, itemsperrow)
            if cantitems > itemsperrow:
                cols = itemsperrow
            else:
                cols = cantitems
            pad = 5 # pixels de padding entre objetos
            aspectw = 9
            aspecth = 8
            itemw = Ceil(width/aspectw)
            itemh = Ceil(height/aspecth)
            # calcular recuadro en funcion a la cantidad de items
            fontheight = fontsize + 4
            xback = 10
            yback = 10
            wback = (itemw + 2*pad) * cols
            hback = (itemh + 2*pad + fontheight) * rows
            self.drawRect(xback,yback,wback,hback,backinvcolor) # recuadro de fondo 
            
            i = 0 # indice del item en la lista de items
            for r in range(0,rows): # por cada fila del cuadro (comienza desde cero)
                for c in range(0,cols): # por cada columna del cuadro (comienza desde cero)
                    if i < cantitems:
                        x = (xback + pad) + (itemw + pad) * c
                        y = (yback + pad) + (itemh + pad + fontheight) * r
                        self.drawRect(x,y,itemw,itemh,backitemcolor) # recuadro del item
                        imagefile = inventory[listaitems[i]]['image']
                        self.drawItem(x,y,itemw,itemh,imagefile)
                        xt = x
                        yt = y + itemh + pad
                        item = listaitems[i]
                        self.drawText(item, textcolor, xt, yt)
                    i += 1

    # Mostrar fondo
    def draw_screen(self):
        # pintar fondo del room en la pantalla
        self.screen.blit(background, (0, 0))
        #screen.blit(text, (textX, textY) )

        # dibujar bloqueos activos
        self.draw_blockages()

        # Actualizar sprites
        sprites.draw(self.screen)

        # Superponer layers de objetos que tapen al player
        self.draw_layers()

        # Caja translucida para el textInput
        self.drawRect(textinputX-3,textinputY-3,maxstringlength*9,fontsize+8,backtextcolor)
        # Blit textInput surface onto the screen
        self.screen.blit(textinput.get_surface(), (textinputX, textinputY))

        # ver donde estan los pies
        #footxy = player.getFootXY()
        #pygame.draw.circle(screen, (255,0,0), (footxy[0],footxy[1]), 3)
        
        # Si el inventario esta activo, mostrarlo
        if show_inventory == True:
            self.drawInventory()
        # Si hay un mensaje global, mostrarlo
        if show_message == True:
            self.drawMessage()
        # Actualizar pantalla con los elementos de screen
        pygame.display.update()

    def draw_layers(self):
        if ('layers' in rooms[currentRoom].keys()):
        #if bool(rooms[currentRoom]['layers']):
            layers = rooms[currentRoom]['layers']
            for layer in layers:
                #print ( layer )
                #print ( layers[layer]['z'] )
                z = self.relativeH( layers[layer]['z'] )
                xfrom = self.relativeW( layers[layer]['xfrom'] )
                xto = self.relativeW( layers[layer]['xto'] )
                layerimage = layers[layer]['layerimage']
                # determino si el player se superpone con este layer
                if player.isEclipsedByLayer(z, xfrom, xto):
                    log('DEBUG',layer,z,xfrom,xto,layerimage)
                    imlayer = loadImage(layerimage, width, height) # devuelve Surface
                    self.screen.blit(imlayer, (0, 0))

    def draw_blockages(self):
        if ('blockages' in rooms[currentRoom].keys()):
            blockages = rooms[currentRoom]['blockages']
            for blockage in blockages:
                active = blockages[blockage]['active']
                # solo dibujo los bloqueos activos
                if active == True:
                    blockimage = blockages[blockage]['blockimage']
                    imblock = loadImage(blockimage, width, height) # devuelve Surface
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
        global rooms
        rooms = {
            'Forest' : {
                'desc' : 'You are in a deep and millenary forest.',
                'background' : 'images/bosque.jpg',
                'imagemap' : 'images/bosque_map.jpg',
                'directions' : {
                   '1' : 'Beach',
                   '2' : 'ForestBif'
                  },
                'from' : {
                    '' : [80, 1000, Dir.E],
                    'ForestBif' : [80, 1000, Dir.E],
                    'Beach' : [1845, 1040, Dir.W]
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
                       'desc' : 'some magical blockage over the bridge. Yo cannot pass through it.',
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
        global inventory
        global ghostitems
        # start with nothing on you
        inventory = {}

        # dictionary of items that will be available later on
        ghostitems = {
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
        global run
        global textX
        global textY
        global show_inventory
        global textinput
        global dirtyscreen
        while run: # Game Loop
            dt = clock.tick(FPS) / 1000 # Returns milliseconds between each call to 'tick'. The convert time to seconds.
            #pygame.time.delay(100)
            dirtyscreen = False
            events = pygame.event.get() # para el textInput
            
            for event in events:
                if (event.type == pygame.QUIT):
                    run = False
                if (event.type == pygame.KEYUP):
                    if (event.key == pygame.K_ESCAPE):
                        events.remove(event) # no imprimo este caracter
                        run = False
                    if (event.key == pygame.K_TAB):
                        show_inventory = False
                        dirtyscreen = True
                        events.remove(event) # no imprimo este caracter
                    if (event.key == pygame.K_F1):
                        self.showHelp()
                    if (event.key == pygame.K_F3):
                        largo = len(previoustext)
                        if (largo > 0):
                            textinput.input_string = previoustext # repetir el ultimo comando
                            textinput.cursor_position = largo
                if (event.type == pygame.KEYDOWN):
                    if (event.key == pygame.K_ESCAPE):
                        events.remove(event) # no imprimo este caracter
                        run = False
                    if (event.key == pygame.K_TAB):
                        show_inventory = True
                        dirtyscreen = True
                        events.remove(event) # no imprimo este caracter
                
            # Feed textInput with events every frame
            texto1 = textinput.get_text()
            if textinput.update(events): # capturar texto con ENTER
                texto = textinput.get_text()
                #texto = filter_nonprintable(texto)
                if len(texto)>0:
                    textinput.clear_text()
                    # Procesar comando ingresado
                    previoustext = texto
                    self.procesarComando(texto)
            
            texto2 = textinput.get_text()
            if texto1 != texto2:
                dirtyscreen = True
            
            player_moved = False
            if keys_allowed:
                keys = pygame.key.get_pressed()
                player_moved = player.update(keys) # actualizo el sprite jugador segun las teclas
                if player_moved:
                    dirtyscreen = True

            if show_message:
                dirtyscreen = True
            self.updateMessage()
            
            if dirtyscreen: # intentar no refrecar todo el tiempo si no es necesario
                self.draw_screen()

        self.doQuit()

    def saveGame(self, file='default.json'):
        # Guardar: room actual, coordenadas foot del player, inventory, ghostinv....
        # ¿como hacer para guardar estado de los items del room? Por ahora, guardo rooms completo.
        # armo un JSON state que contenga los demas elementos
        state = {}
        state['inventory'] = inventory
        state['rooms'] = rooms
        state['ghostinv'] = ghostitems
        state['player'] = player.saveState()
        state['currentRoom'] = currentRoom
        print(state) # impresion de Python
        print(json.dumps(state)) # impresion de modulo json
        with open(file, 'w') as outfile:
            json.dump(state, outfile)
        
    def loadGame(self, file='default.json'):
        global inventory
        global rooms
        global ghostitems
        log('DEBUG', 'load')
        with open(file) as json_file:
            state = json.load(json_file)
        print(state)
        inventory = state['inventory']
        rooms = state['rooms']
        ghostitems = state['ghostinv']
        playerstate = state['player']
        room = state['currentRoom']
        self.goToRoom(room)        
        player.loadState(playerstate)
        
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

def Ceil(number): # reemplazo de math.ceil()
    #return int(-1 * number // 1 * -1)
    res = int(number)
    return res if res == number or number < 0 else res+1

def CeilDivision(number1, number2):
    # OJO: math.ceil() Returns an int value in Python 3+, while it returns a float in Python 2.
    # -(-3//2) da 2
    return -(-number1 // number2)

# EJ: print (randomString(['uno','dos','tres','cuatro']))
def randomString(stringList):
    selected = random.choice(stringList)
    return selected

def filter_nonprintable(texto):
    log('DEBUG','antes  : '+texto)
    #textof = filter(lambda x: x in string.printable, texto) # filtrar caracteres no imprimibles
    textof = ''.join(c for c in texto if not unicodedata.category(c).startswith('C'))
    log('DEBUG','despues: '+textof)
    return textof


if __name__ == "__main__":
    main()
