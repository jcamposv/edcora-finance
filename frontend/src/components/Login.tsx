import React, { useState } from 'react';
import { whatsappApi } from '../lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { InputOTP, InputOTPGroup, InputOTPSeparator, InputOTPSlot } from '@/components/ui/input-otp';
import { ArrowLeft, Smartphone } from 'lucide-react';

interface LoginProps {
  onLogin: (phoneNumber: string) => void;
}

const Login: React.FC<LoginProps> = ({ onLogin }) => {
  const [phoneNumber, setPhoneNumber] = useState('');
  const [otpCode, setOtpCode] = useState('');
  const [otpSent, setOtpSent] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSendOTP = async () => {
    if (!phoneNumber) return;
    
    setIsLoading(true);
    setError(null);

    try {
      await whatsappApi.sendOTP(phoneNumber);
      setOtpSent(true);
    } catch (error) {
      console.error('Error sending OTP:', error);
      setError('Error enviando código. Verifica tu número de teléfono.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleVerifyOTP = async () => {
    if (otpCode.length !== 6) return;
    
    setIsLoading(true);
    setError(null);

    try {
      await whatsappApi.verifyOTP(phoneNumber, otpCode);
      onLogin(phoneNumber);
    } catch (error) {
      console.error('Error verifying OTP:', error);
      setError('Código inválido. Por favor, intenta de nuevo.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleBack = () => {
    setOtpSent(false);
    setOtpCode('');
    setError(null);
  };

  if (!otpSent) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 p-4">
        <Card className="w-full max-w-md">
          <CardHeader className="text-center">
            <div className="mx-auto w-12 h-12 bg-green-100 rounded-full flex items-center justify-center mb-4">
              <Smartphone className="h-6 w-6 text-green-600" />
            </div>
            <CardTitle>Control de Finanzas</CardTitle>
            <CardDescription>
              Ingresa tu número de WhatsApp para continuar
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {error && (
              <div className="bg-destructive/15 text-destructive text-sm p-3 rounded-md">
                {error}
              </div>
            )}
            <div className="space-y-2">
              <Label htmlFor="phone">Número de WhatsApp</Label>
              <Input
                id="phone"
                type="tel"
                placeholder="+52 123 456 7890"
                value={phoneNumber}
                onChange={(e) => setPhoneNumber(e.target.value)}
                className="text-center text-lg"
              />
              <p className="text-xs text-muted-foreground text-center">
                Incluye el código de país (ej: +52 para México)
              </p>
            </div>
          </CardContent>
          <CardFooter>
            <Button 
              className="w-full" 
              onClick={handleSendOTP}
              disabled={!phoneNumber || isLoading}
            >
              {isLoading ? "Enviando..." : "Enviar Código de Verificación"}
            </Button>
          </CardFooter>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center relative">
          <Button 
            variant="ghost" 
            size="icon" 
            className="absolute left-0 top-0"
            onClick={handleBack}
          >
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div className="mx-auto w-12 h-12 bg-green-100 rounded-full flex items-center justify-center mb-4">
            <Smartphone className="h-6 w-6 text-green-600" />
          </div>
          <CardTitle>Ingresa el código de verificación</CardTitle>
          <CardDescription>
            Enviamos un código de 6 dígitos a {phoneNumber}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {error && (
            <div className="bg-destructive/15 text-destructive text-sm p-3 rounded-md">
              {error}
            </div>
          )}
          <div className="flex justify-center">
            <InputOTP
              maxLength={6}
              value={otpCode}
              onChange={setOtpCode}
            >
              <InputOTPGroup>
                <InputOTPSlot index={0} />
                <InputOTPSlot index={1} />
                <InputOTPSlot index={2} />
              </InputOTPGroup>
              <InputOTPSeparator />
              <InputOTPGroup>
                <InputOTPSlot index={3} />
                <InputOTPSlot index={4} />
                <InputOTPSlot index={5} />
              </InputOTPGroup>
            </InputOTP>
          </div>
          <div className="text-center">
            <Button variant="link" className="text-sm text-muted-foreground" onClick={handleSendOTP}>
              ¿No recibiste el código? Reenviar
            </Button>
          </div>
        </CardContent>
        <CardFooter>
          <Button 
            className="w-full" 
            onClick={handleVerifyOTP}
            disabled={otpCode.length !== 6 || isLoading}
          >
            {isLoading ? "Verificando..." : "Verificar Código"}
          </Button>
        </CardFooter>
      </Card>
    </div>
  );
};

export default Login;